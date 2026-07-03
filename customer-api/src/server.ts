import cors from "cors";
import express from "express";
import {
  CORS_ALLOWED_ORIGINS,
  CUSTOMER_API_PORT,
  CUSTOMER_PROFILE_COLLECTION,
  getDb,
} from "./db.js";

const app = express();
app.use(cors({ origin: CORS_ALLOWED_ORIGINS }));

// GET /clients — versão resumida para o seletor de clientes da sidebar (nunca
// devolve claims/policies completos, ver GET /clients/:customerId para o perfil cheio).
app.get("/clients", async (_req, res) => {
  const db = await getDb();
  const docs = await db
    .collection(CUSTOMER_PROFILE_COLLECTION)
    .find(
      {},
      {
        projection: {
          _id: 0,
          customer_id: 1,
          name: 1,
          "policies.policy_id": 1,
          "policies.type": 1,
          contact_preference: 1,
          "claims.status": 1,
        },
      }
    )
    .toArray();

  const clients = docs.map((doc) => {
    const claims = (doc.claims as { status: string }[] | undefined) || [];
    const { claims: _claims, ...rest } = doc;
    return {
      ...rest,
      open_claims_count: claims.filter((c) => c.status === "em_analise").length,
    };
  });

  res.json(clients);
});

// GET /clients/:customerId — perfil completo, mesmo schema que ai-agent lê em load_memory.
app.get("/clients/:customerId", async (req, res) => {
  const db = await getDb();
  const doc = await db
    .collection(CUSTOMER_PROFILE_COLLECTION)
    .findOne({ customer_id: req.params.customerId }, { projection: { _id: 0 } });

  if (!doc) {
    res.status(404).json({ detail: "Cliente não encontrado" });
    return;
  }

  res.json(doc);
});

app.listen(CUSTOMER_API_PORT, () => {
  console.log(`customer-api ouvindo em http://localhost:${CUSTOMER_API_PORT}`);
});
