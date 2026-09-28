import { describe, expect, it } from "vitest";

describe("hosted AInimity configuration", () => {
  it("exposes a healthy five-role council with Supabase configuration enabled", async () => {
    const response = await fetch("http://127.0.0.1:3000/api/health");
    expect(response.ok).toBe(true);
    const payload = await response.json() as {
      status: string;
      supabase_auth: boolean;
      configured_agents: string[];
      role_specific_agents: string[];
      general_fallback_configured: boolean;
      features: string[];
    };
    expect(payload.status).toBe("ok");
    expect(payload.supabase_auth).toBe(true);
    expect(payload.configured_agents).toEqual(
      expect.arrayContaining(["strategist", "technical", "adversarial", "human_mind", "validator"]),
    );
    expect(payload.role_specific_agents).toEqual(
      expect.arrayContaining(["strategist", "technical", "adversarial", "human_mind", "validator"]),
    );
    expect(payload.general_fallback_configured).toBe(true);
    expect(payload.features).toEqual(expect.arrayContaining([
      "evidence-retrieval",
      "citation-aware-validation",
      "argument-graph-memory",
      "explicit-image-analysis",
    ]));

    const configResponse = await fetch("http://127.0.0.1:3000/api/config");
    expect(configResponse.ok).toBe(true);
    const config = await configResponse.json() as { supabase_storage_bucket: string };
    expect(config.supabase_storage_bucket).toBe("council-documents");
  });
});
