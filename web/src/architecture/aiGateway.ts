import type { HostSnapshot } from "./hostView";

export type AICapability =
  | "explain_signal"
  | "summarize_market"
  | "summarize_timeline"
  | "explain_health";

export type AIProviderStatus = "available" | "unavailable" | "error";

export type AIResponseStatus =
  | "SUCCESS"
  | "UNAVAILABLE"
  | "PERMISSION_DENIED"
  | "ERROR";

export interface AllowedContextSummary {
  contextId: string;
  userId: string;
  capability: AICapability;
  timestamp: number;
  permittedSymbol?: string | null;
  hasPermittedSignal: boolean;
  hasPermittedMarket: boolean;
  permittedTimelineCount: number;
  hasPermittedHealth: boolean;
  isSanitized: boolean;
  metadata: Record<string, unknown>;
}

export interface AIRequestPayload {
  requestId: string;
  userId: string;
  capability: AICapability;
  targetSymbol?: string | null;
  promptQuery?: string | null;
}

export interface AIResponsePayload {
  requestId: string;
  status: AIResponseStatus;
  capability: AICapability;
  providerName: string;
  content: string;
  createdAt: number;
  contextSummary?: AllowedContextSummary | null;
  errorMessage?: string | null;
}

export function buildAllowedContextSummary(
  snapshot: HostSnapshot,
  capability: AICapability,
  targetSymbol?: string
): AllowedContextSummary {
  const userId = snapshot.security?.userId || "guest_user";
  const sym = targetSymbol || snapshot.market.symbol;

  const hasSignal = Boolean(
    capability === "explain_signal" &&
      snapshot.signal &&
      snapshot.signal.action &&
      snapshot.signal.action !== "NO SIGNAL"
  );

  const hasMarket = Boolean(
    capability === "summarize_market" && snapshot.market
  );

  const timelineCount =
    capability === "summarize_timeline" && snapshot.activity
      ? snapshot.activity.length
      : 0;

  const hasHealth = Boolean(
    capability === "explain_health" && snapshot.platform
  );

  return {
    contextId: `ctx_fe_${Math.random().toString(36).substring(2, 9)}`,
    userId,
    capability,
    timestamp: Date.now() / 1000,
    permittedSymbol: sym,
    hasPermittedSignal: hasSignal,
    hasPermittedMarket: hasMarket,
    permittedTimelineCount: timelineCount,
    hasPermittedHealth: hasHealth,
    isSanitized: true,
    metadata: {
      source: "AIGatewayFrontendBoundary",
      role: snapshot.security?.role || "user",
    },
  };
}

export function processAIGatewayRequest(
  snapshot: HostSnapshot,
  request: AIRequestPayload,
  providerOverride?: { status: AIProviderStatus; name: string; responseText?: string }
): AIResponsePayload {
  const now = Date.now() / 1000;
  const context = buildAllowedContextSummary(
    snapshot,
    request.capability,
    request.targetSymbol || undefined
  );

  // Check authorization
  const permissions = snapshot.security?.permissions || [];
  const isAdmin = snapshot.security?.isAdmin || false;
  const hasSignalPermission =
    isAdmin || permissions.includes("read:signals") || permissions.includes("admin:all");

  if (!hasSignalPermission) {
    return {
      requestId: request.requestId,
      status: "PERMISSION_DENIED",
      capability: request.capability,
      providerName: providerOverride?.name || "UnavailableAIProviderAdapter",
      content: "Access denied: missing required permissions to access AI context for this capability.",
      createdAt: now,
      contextSummary: null,
      errorMessage: "Missing required permissions.",
    };
  }

  // Check provider status
  const providerStatus = providerOverride?.status || "unavailable";
  const providerName = providerOverride?.name || "UnavailableAIProviderAdapter";

  if (providerStatus !== "available") {
    return {
      requestId: request.requestId,
      status: "UNAVAILABLE",
      capability: request.capability,
      providerName,
      content: "AI unavailable / provider not configured",
      createdAt: now,
      contextSummary: context,
      errorMessage: "No external AI provider adapter attached.",
    };
  }

  return {
    requestId: request.requestId,
    status: "SUCCESS",
    capability: request.capability,
    providerName,
    content: providerOverride?.responseText || "AI explanation generated successfully.",
    createdAt: now,
    contextSummary: context,
  };
}
