"use client";
/**
 * useOAuthPopup — drive the one-click flow from the dashboard (YH9AE4D).
 *
 * The popup posts a verdict back with postMessage and closes itself. We listen
 * for that message, but we ALSO poll popup.closed, because there are two ways
 * the message never arrives and both are common in practice:
 *   · the user closes the window manually mid-consent
 *   · a browser blocks the postMessage across an origin boundary
 * Without the poll the UI would sit on "Connecting…" forever. With it, closing
 * the popup always resolves the flow — worst case we re-fetch status and find
 * nothing changed, which is the correct outcome for an abandoned attempt.
 *
 * The message carries NO token — only {ok, platform, message}. The authoritative
 * new state always comes from re-fetching /status over the owner-authenticated
 * API, so a spoofed postMessage can at most show a misleading toast, never
 * fabricate a connection.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { startOAuth } from "@/lib/api";
import type { OAuthPopupMessage } from "@/lib/types";

export type OAuthResult = { ok: boolean; platform: string; message: string };

export function useOAuthPopup(onFinished: (r: OAuthResult) => void) {
  const [connecting, setConnecting] = useState<string | null>(null);
  const popupRef = useRef<Window | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const finishedRef = useRef(false);
  const onFinishedRef = useRef(onFinished);
  onFinishedRef.current = onFinished;

  const cleanup = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    popupRef.current = null;
    setConnecting(null);
  }, []);

  useEffect(() => {
    function onMessage(e: MessageEvent) {
      const data = e.data as OAuthPopupMessage | undefined;
      if (!data || data.source !== "dircomedia-oauth") return;
      finishedRef.current = true;
      cleanup();
      onFinishedRef.current({ ok: data.ok, platform: data.platform, message: data.message });
    }
    window.addEventListener("message", onMessage);
    return () => {
      window.removeEventListener("message", onMessage);
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [cleanup]);

  const connect = useCallback(
    async (platform: string) => {
      if (connecting) return;
      finishedRef.current = false;
      setConnecting(platform);
      try {
        const { authorize_url } = await startOAuth(platform);

        const w = 560;
        const h = 720;
        // Center on the CURRENT screen in a multi-monitor setup — screenX/Y are
        // the window's position in the virtual desktop, so adding them keeps the
        // popup on the monitor the user is actually looking at.
        const left = window.screenX + Math.max(0, (window.outerWidth - w) / 2);
        const top = window.screenY + Math.max(0, (window.outerHeight - h) / 2);

        const popup = window.open(
          authorize_url,
          `dircomedia_oauth_${platform}`,
          `width=${w},height=${h},left=${Math.round(left)},top=${Math.round(top)},resizable=yes,scrollbars=yes`
        );

        if (!popup) {
          cleanup();
          onFinishedRef.current({
            ok: false,
            platform,
            message:
              "Your browser blocked the popup. Allow popups for this site and press Connect again.",
          });
          return;
        }

        popupRef.current = popup;
        pollRef.current = setInterval(() => {
          if (popupRef.current?.closed) {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            if (!finishedRef.current) {
              // Closed without a verdict — re-check status rather than guessing.
              finishedRef.current = true;
              cleanup();
              onFinishedRef.current({
                ok: false,
                platform,
                message: "Authorization window closed. Checking connection status…",
              });
            }
          }
        }, 700);
      } catch (e) {
        cleanup();
        onFinishedRef.current({
          ok: false,
          platform,
          message: e instanceof Error ? cleanError(e.message) : "Could not start the connection.",
        });
      }
    },
    [connecting, cleanup]
  );

  return { connect, connecting };
}

/** API errors arrive as `API 400: {"detail":"…"}`. Show the human part. */
export function cleanError(raw: string): string {
  // [\s\S] rather than the /s flag — the tsconfig target predates es2018.
  const m = raw.match(/API \d+: ([\s\S]*)/);
  const body = m ? m[1] : raw;
  try {
    const parsed = JSON.parse(body);
    if (typeof parsed?.detail === "string") return parsed.detail;
    if (Array.isArray(parsed?.detail)) return parsed.detail.map((d: { msg?: string }) => d.msg).join("; ");
  } catch {
    /* not JSON — fall through */
  }
  return body.slice(0, 400);
}
