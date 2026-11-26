const DEFAULT_RUNNER_URL = "http://45c28620-fabrica-software:9877";

function bridgeError(code) {
  return Object.assign(new Error(code), { code });
}

export function createRunnerBridge({
  token = process.env.FACTORY_RUNNER_DISPATCH_TOKEN || "",
  baseUrl = DEFAULT_RUNNER_URL,
  fetchImpl = globalThis.fetch
} = {}) {
  let endpoint;
  try {
    endpoint = new URL(baseUrl);
  } catch {
    endpoint = null;
  }
  const endpointAllowed = Boolean(
    endpoint &&
    endpoint.protocol === "http:" &&
    endpoint.hostname === "45c28620-fabrica-software" &&
    endpoint.port === "9877" &&
    endpoint.pathname === "/" &&
    !endpoint.username &&
    !endpoint.password
  );
  const configured = typeof token === "string" && token.length >= 32 &&
    endpointAllowed && typeof fetchImpl === "function";

  async function request(path, init = {}) {
    if (!configured) throw bridgeError("runner_not_configured");
    let response;
    try {
      response = await fetchImpl(new URL(path, endpoint), {
        ...init,
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-Portal-Dispatch-Token": token,
          ...(init.headers || {})
        },
        cache: "no-store",
        signal: AbortSignal.timeout(4000)
      });
    } catch {
      throw bridgeError("runner_unavailable");
    }
    let data;
    try {
      data = await response.json();
    } catch {
      throw bridgeError("runner_invalid_response");
    }
    if (!response.ok) {
      const code = typeof data?.error === "string" &&
        /^[a-z][a-z0-9_]{0,63}$/.test(data.error)
        ? data.error
        : "runner_request_failed";
      throw bridgeError(code);
    }
    return data;
  }

  return {
    configured,
    async submitMission({ missionId, projectId, prompt, createdAt }) {
      return request("/v1/jobs", {
        method: "POST",
        body: JSON.stringify({
          mission_id: missionId,
          project_id: projectId,
          prompt,
          created_at: createdAt
        })
      });
    },
    async getJob(executionId) {
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(executionId || "")) {
        throw bridgeError("invalid_execution_id");
      }
      return request("/v1/jobs/" + encodeURIComponent(executionId), {
        method: "GET",
        headers: { "Content-Type": "application/json" }
      });
    }
  };
}
