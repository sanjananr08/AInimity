/**
 * Optional MongoDB adapter for human-reviewed decision snapshots.
 *
 * The core AInimity app remains fully usable with SQLite + Supabase. This
 * adapter is intentionally opt-in: set MONGODB_URI and call connect() from a
 * host or worker that needs cross-run analytics. It never logs credentials
 * and it never silently falls back to a remote database.
 */
export class DecisionSnapshotRepository {
  constructor({ uri = process.env.MONGODB_URI, database = process.env.MONGODB_DATABASE || 'ainimity', collection = process.env.MONGODB_COLLECTION || 'decision_snapshots' } = {}) {
    this.uri = uri;
    this.databaseName = database;
    this.collectionName = collection;
    this.client = null;
    this.collection = null;
  }

  async connect() {
    if (!this.uri) throw new Error('MONGODB_URI is not configured; MongoDB integration is opt-in.');
    let MongoClient;
    try {
      ({ MongoClient } = await import('mongodb'));
    } catch {
      throw new Error('Install the optional mongodb package before enabling this adapter.');
    }
    this.client = new MongoClient(this.uri, { serverSelectionTimeoutMS: 5000 });
    await this.client.connect();
    this.collection = this.client.db(this.databaseName).collection(this.collectionName);
    await this.collection.createIndex({ userId: 1, createdAt: -1 });
    return this;
  }

  async save(snapshot) {
    if (!this.collection) throw new Error('Call connect() before saving a snapshot.');
    const safe = {
      userId: String(snapshot.userId),
      objective: String(snapshot.objective || '').slice(0, 4000),
      mode: String(snapshot.mode || 'unknown'),
      humanDecision: String(snapshot.humanDecision || '').slice(0, 4000),
      outcome: snapshot.outcome ? String(snapshot.outcome).slice(0, 4000) : null,
      createdAt: new Date(),
    };
    const result = await this.collection.insertOne(safe);
    return { id: result.insertedId.toString(), ...safe };
  }

  async listByUser(userId, limit = 50) {
    if (!this.collection) throw new Error('Call connect() before listing snapshots.');
    return this.collection.find({ userId: String(userId) }).sort({ createdAt: -1 }).limit(Math.min(Number(limit) || 50, 200)).toArray();
  }

  async close() {
    await this.client?.close();
    this.client = null;
    this.collection = null;
  }
}
