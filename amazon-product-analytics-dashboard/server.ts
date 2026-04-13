import express from "express";
import { createServer as createViteServer } from "vite";
import path from "path";
import fs from "fs/promises";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(express.json());

  const DATA_DIR = path.join(__dirname, "src", "data", "dashboards");

  // Ensure data directory exists
  try {
    await fs.mkdir(DATA_DIR, { recursive: true });
  } catch (err) {
    console.error("Error creating data directory:", err);
  }

  // API: List all dashboards
  app.get("/api/dashboards", async (req, res) => {
    try {
      const files = await fs.readdir(DATA_DIR);
      const dashboards = await Promise.all(
        files
          .filter((f) => f.endsWith(".json"))
          .map(async (f) => {
            const content = await fs.readFile(path.join(DATA_DIR, f), "utf-8");
            const data = JSON.parse(content);
            return {
              id: data.id,
              title: data.title,
              market: data.market,
              group: data.group || 'detailed',
            };
          })
      );
      res.json({ dashboards });
    } catch (err) {
      res.status(500).json({ error: "Failed to list dashboards" });
    }
  });

  // API: Get specific dashboard data
  app.get("/api/dashboards/:id", async (req, res) => {
    try {
      const filePath = path.join(DATA_DIR, `${req.params.id}.json`);
      const content = await fs.readFile(filePath, "utf-8");
      res.json(JSON.parse(content));
    } catch (err) {
      res.status(404).json({ error: "Dashboard not found" });
    }
  });

  // API: Upload/Save dashboard data
  app.post("/api/dashboards", async (req, res) => {
    try {
      const data = req.body;
      if (!data.id) return res.status(400).json({ error: "ID is required" });
      
      const filePath = path.join(DATA_DIR, `${data.id}.json`);
      await fs.writeFile(filePath, JSON.stringify(data, null, 2));
      res.json({ success: true });
    } catch (err) {
      res.status(500).json({ error: "Failed to save dashboard" });
    }
  });

  // Vite middleware for development
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
