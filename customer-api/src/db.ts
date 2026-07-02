import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";
import { MongoClient, type Db } from "mongodb";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Vars próprias deste serviço (porta, CORS) vivem em customer-api/.env; as
// credenciais de Mongo são compartilhadas com o resto do projeto e vivem no
// .env da raiz do repo — dotenv.config() nunca sobrescreve uma env var já
// definida, então a segunda chamada só preenche o que faltar (MONGODB_URI etc).
dotenv.config({ path: path.resolve(__dirname, "../.env") });
dotenv.config({ path: path.resolve(__dirname, "../../.env") });

export const MONGODB_URI = process.env.MONGODB_URI!;
export const MONGODB_DB_NAME = process.env.MONGODB_DB_NAME || "claraseg";
export const CUSTOMER_API_PORT = Number(process.env.CUSTOMER_API_PORT || 8090);
export const CORS_ALLOWED_ORIGINS = (
  process.env.CORS_ALLOWED_ORIGINS || "http://localhost:5173"
).split(",");

export const CUSTOMER_PROFILE_COLLECTION = "customer_profile";

if (!MONGODB_URI) {
  throw new Error("MONGODB_URI não definido (verifique o .env na raiz do repo)");
}

let client: MongoClient | null = null;

export async function getDb(): Promise<Db> {
  if (!client) {
    client = new MongoClient(MONGODB_URI);
    await client.connect();
  }
  return client.db(MONGODB_DB_NAME);
}
