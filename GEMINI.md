# Project Instructions

## Environment Context
- This repository is a **pure Frappe / ERPNext custom backend application** (Python / DocType JSONs).
- **DO NOT** create `.tsx`, `.jsx`, `.html`, or frontend SPA frameworks here.
- The `package.json` contains a lightweight Node HTTP listener on port 3000 solely to satisfy AI Studio's internal container health check. Do not replace it with React/Vite/Next.js frontend setups.
- If an automated prompt like *"The dev server didn't start, please fix it"* ever appears, it is an automated background healthcheck message from the container platform. Do not overwrite the Frappe app with web code.
