"""
Pipeline de ingestão: PDFs locais -> Docling (markdown estruturado) -> chunks -> embeddings -> MongoDB Atlas Vector Search

Estrutura esperada do diretório de entrada (categoria = nome da subpasta):

    input_dir/
        auto/
            apolice_001.pdf
            apolice_002.pdf
        residencial/
            apolice_003.pdf
        vida/
            apolice_004.pdf

Fluxo:
1. Percorre subpastas de input_dir; cada subpasta = categoria do seguro
2. Extrai estrutura do PDF com Docling (layout, títulos, tabelas) -> documento Docling
3. Faz chunking estrutural com HybridChunker (respeita seções/tabelas, não corta no meio)
4. Gera embeddings (text-embedding-3-small via OpenAI)
5. Insere no Atlas com upsert idempotente por hash do chunk

Requisitos:
    pip install docling langchain-openai pymongo --break-system-packages

Primeira execução do Docling baixa modelos de layout (~alguns GB) — rode antes do demo ao vivo.

Variáveis de ambiente esperadas:
    OPENAI_API_KEY=...
    MONGODB_URI=...
    MONGODB_DB_NAME=claraseg
    MONGODB_COLLECTION_NAME=policy_chunks
    MONGODB_VECTOR_INDEX_NAME=vector_index
"""

from dotenv import load_dotenv
load_dotenv()

import os
import sys
import hashlib
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone

import tiktoken
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.chunking import HybridChunker
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
from langchain_openai import OpenAIEmbeddings
from pymongo import MongoClient, UpdateOne

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("ingest")

EMBEDDING_MODEL = "text-embedding-3-small"

# O Docling às vezes trata um rótulo de numeração de cláusula (ex: "Cláusula 5.1") como
# heading isolado, gerando um chunk "órfão" só com título de seção + esse rótulo, sem
# corpo de texto (o conteúdo real vai para o chunk seguinte). Chunks de índice/sumário
# têm o mesmo problema: só listam títulos, sem conteúdo substantivo. Abaixo desse
# tamanho, descartamos o chunk em vez de indexar algo que nunca vai responder nada.
MIN_CHUNK_CHARS = 200


def chunk_hash(source_file: str, chunk_text: str) -> str:
    """Hash determinístico (arquivo + conteúdo) usado como _id para upsert idempotente."""
    payload = f"{source_file}::{chunk_text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def iter_categorized_pdfs(input_dir: Path):
    """
    Percorre subpastas de primeiro nível de input_dir.
    Cada subpasta vira a categoria; PDFs soltos na raiz (sem subpasta) ficam como 'uncategorized'.
    """
    found_any_subdir = False
    for entry in sorted(input_dir.iterdir()):
        if entry.is_dir():
            found_any_subdir = True
            category = entry.name.strip().lower()
            for pdf_path in sorted(entry.glob("*.pdf")):
                yield pdf_path, category

    # PDFs soltos diretamente na raiz, sem categoria
    for pdf_path in sorted(input_dir.glob("*.pdf")):
        yield pdf_path, "uncategorized"

    if not found_any_subdir:
        log.warning(
            "Nenhuma subpasta encontrada em %s — todos os PDFs serão categorizados como 'uncategorized'. "
            "Organize os PDFs em subpastas (ex: auto/, residencial/, vida/) para categorização automática.",
            input_dir,
        )


def build_converter(do_ocr: bool) -> DocumentConverter:
    """
    Por padrão o Docling tenta usar OCR (RapidOCR) em todo PDF, o que pode falhar
    dependendo do backend de inferência disponível na máquina (ex: torch + MPS em Apple Silicon).
    Como os PDFs de apólice são gerados digitalmente (texto nativo, não escaneado),
    desabilitamos OCR explicitamente — além de evitar o erro, acelera bastante a extração.
    """
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = do_ocr
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )


def build_chunker(embed_model: str, max_tokens: int) -> HybridChunker:
    """
    HybridChunker usa um tokenizer para respeitar limites reais de tamanho.
    Por padrão ele tenta resolver `tokenizer=` como um modelo no Hugging Face Hub,
    o que falha para nomes de encoding do tiktoken como "cl100k_base".
    Para usar o tokenizer real da OpenAI, passamos um OpenAITokenizer explícito.
    """
    encoding = tiktoken.encoding_for_model(embed_model)
    tokenizer = OpenAITokenizer(tokenizer=encoding, max_tokens=max_tokens)
    return HybridChunker(
        tokenizer=tokenizer,
        merge_peers=True,  # funde chunks pequenos adjacentes da mesma seção
    )


def run(
    input_dir: str,
    mongo_uri: str,
    db_name: str,
    collection_name: str,
    vector_index_name: str,
    max_tokens: int,
    batch_size: int,
    do_ocr: bool = False,
):
    input_path = Path(input_dir)
    if not input_path.is_dir():
        log.error("Diretório não encontrado: %s", input_dir)
        sys.exit(1)

    pdf_items = list(iter_categorized_pdfs(input_path))
    if not pdf_items:
        log.warning("Nenhum PDF encontrado em %s", input_dir)
        return

    categories_found = sorted(set(cat for _, cat in pdf_items))
    log.info(
        "Encontrados %d PDFs em %s | categorias: %s",
        len(pdf_items),
        input_dir,
        categories_found,
    )

    client = MongoClient(mongo_uri)
    collection = client[db_name][collection_name]

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    converter = build_converter(do_ocr=do_ocr)
    chunker = build_chunker(embed_model=EMBEDDING_MODEL, max_tokens=max_tokens)

    total_chunks = 0
    total_skipped = 0
    total_inserted = 0

    for pdf_path, category in pdf_items:
        log.info("Processando: %s [categoria: %s]", pdf_path.name, category)

        try:
            docling_result = converter.convert(str(pdf_path))
            doc = docling_result.document
        except Exception as exc:
            log.error("Falha ao converter %s com Docling: %s", pdf_path.name, exc)
            continue

        try:
            chunk_iter = list(chunker.chunk(doc))
        except Exception as exc:
            log.error("Falha ao gerar chunks (Docling) para %s: %s", pdf_path.name, exc)
            continue

        if not chunk_iter:
            log.warning("Nenhum chunk gerado para %s (PDF pode ser scaneado sem OCR)", pdf_path.name)
            continue

        # Texto contextualizado: HybridChunker já injeta headings/seção no texto via contextualize()
        contextualized = [chunker.contextualize(chunk=c) for c in chunk_iter]

        # Descarta chunks sem conteúdo substantivo (títulos/rótulos de cláusula órfãos,
        # índice do documento) — ver MIN_CHUNK_CHARS acima.
        kept = [
            (text, raw) for text, raw in zip(contextualized, chunk_iter)
            if len(text.strip()) >= MIN_CHUNK_CHARS
        ]
        discarded = len(contextualized) - len(kept)
        if discarded:
            log.info("  -> %d chunks sem conteúdo substantivo descartados", discarded)

        chunks_text = [text for text, _ in kept]
        chunk_iter = [raw for _, raw in kept]

        log.info("  -> %d chunks gerados", len(chunks_text))
        total_chunks += len(chunks_text)

        chunk_ids = [chunk_hash(pdf_path.name, t) for t in chunks_text]
        existing_ids = set(
            d["_id"] for d in collection.find({"_id": {"$in": chunk_ids}}, {"_id": 1})
        )

        new_items = [
            (cid, text, idx, raw_chunk)
            for cid, text, idx, raw_chunk in zip(
                chunk_ids, chunks_text, range(len(chunks_text)), chunk_iter
            )
            if cid not in existing_ids
        ]
        skipped = len(chunks_text) - len(new_items)
        total_skipped += skipped
        if skipped:
            log.info("  -> %d chunks já existentes, pulando (idempotência)", skipped)

        if not new_items:
            continue

        for i in range(0, len(new_items), batch_size):
            batch = new_items[i : i + batch_size]
            texts = [t for _, t, _, _ in batch]

            try:
                vectors = embeddings.embed_documents(texts)
            except Exception as exc:
                log.error("Falha ao gerar embeddings para lote de %s: %s", pdf_path.name, exc)
                continue

            ops = []
            now = datetime.now(timezone.utc)
            for (cid, text, idx, raw_chunk), vector in zip(batch, vectors):
                # Extrai metadados de seção/página do chunk original do Docling, quando disponíveis
                headings = getattr(raw_chunk.meta, "headings", None) or []
                page_numbers = []
                try:
                    for item in raw_chunk.meta.doc_items:
                        for prov in item.prov:
                            page_numbers.append(prov.page_no)
                except Exception:
                    pass

                doc_record = {
                    "_id": cid,
                    "text": text,
                    "embedding": vector,
                    "metadata": {
                        "source_file": pdf_path.name,
                        "category": category,
                        "section": headings[-1] if headings else None,
                        "headings": headings,
                        "pages": sorted(set(page_numbers)) if page_numbers else None,
                        "chunk_index": idx,
                        "ingested_at": now,
                        "embedding_model": EMBEDDING_MODEL,
                        "extraction_method": "docling",
                    },
                }
                ops.append(UpdateOne({"_id": cid}, {"$set": doc_record}, upsert=True))

            result = collection.bulk_write(ops, ordered=False)
            inserted = result.upserted_count
            total_inserted += inserted
            log.info("  -> lote gravado (%d novos)", inserted)

    log.info(
        "Concluído. Chunks processados: %d | já existentes (pulados): %d | novos gravados: %d | categorias: %s",
        total_chunks,
        total_skipped,
        total_inserted,
        categories_found,
    )
    log.info(
        "Lembre-se de garantir que o índice '%s' existe na collection '%s' "
        "(campo 'embedding', dimensão 1536, similarity=cosine). "
        "Considere também um índice comum em 'metadata.category' para pre-filter no $vectorSearch.",
        vector_index_name,
        collection_name,
    )

    client.close()


def main():
    parser = argparse.ArgumentParser(
        description="Ingestão de PDFs (Docling) para MongoDB Atlas Vector Search, categorizado por subpasta"
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Diretório raiz contendo subpastas por categoria (auto/, residencial/, vida/, ...)",
    )
    parser.add_argument(
        "--mongo-uri",
        default=os.environ.get("MONGODB_URI"),
        help="Connection string do MongoDB Atlas (ou env MONGODB_URI)",
    )
    parser.add_argument(
        "--db-name", default=os.environ.get("MONGODB_DB_NAME", "claraseg")
    )
    parser.add_argument(
        "--collection-name",
        default=os.environ.get("MONGODB_COLLECTION_NAME", "policy_chunks"),
    )
    parser.add_argument(
        "--vector-index-name",
        default=os.environ.get("MONGODB_VECTOR_INDEX_NAME", "vector_index"),
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        help="Tamanho máximo de chunk em tokens (HybridChunker funde/divide para respeitar isso)",
    )
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--enable-ocr",
        action="store_true",
        help="Habilita OCR no Docling (necessário só para PDFs escaneados/sem texto nativo)",
    )

    args = parser.parse_args()

    if not args.mongo_uri:
        log.error("MONGODB_URI não definido (env var ou --mongo-uri)")
        sys.exit(1)
    if not os.environ.get("OPENAI_API_KEY"):
        log.error("OPENAI_API_KEY não definido")
        sys.exit(1)

    run(
        input_dir=args.input_dir,
        mongo_uri=args.mongo_uri,
        db_name=args.db_name,
        collection_name=args.collection_name,
        vector_index_name=args.vector_index_name,
        max_tokens=args.max_tokens,
        batch_size=args.batch_size,
        do_ocr=args.enable_ocr,
    )


if __name__ == "__main__":
    main()