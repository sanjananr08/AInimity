# Optional MongoDB decision snapshots

AInimity's core runtime uses FastAPI, SQLite history, and Supabase Auth/Storage. This folder demonstrates an optional Node.js integration for a future analytics or outcome-learning worker.

## Why it is separate

- The public app does not require MongoDB.
- No user data is sent to MongoDB unless a host explicitly imports the adapter and calls `connect()`.
- The adapter stores only a bounded objective, selected mode, human decision, and optional later outcome.
- Credentials are read from environment variables and never printed.

## Enable locally

```bash
npm install
export MONGODB_URI='mongodb+srv://...'
export MONGODB_DATABASE='ainimity'
export MONGODB_COLLECTION='decision_snapshots'
node --input-type=module -e "import { DecisionSnapshotRepository } from './decision-snapshot-repository.mjs'; const repo = await new DecisionSnapshotRepository().connect(); console.log(await repo.listByUser('demo')); await repo.close();"
```

This is intentionally not connected to the live decision pipeline yet. A future version can connect it to a user-confirmed **human decision + actual outcome** review flow, not raw model output.
