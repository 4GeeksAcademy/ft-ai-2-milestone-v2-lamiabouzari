"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { telemetryService } from "@/services/telemetry";

export function TelemetryInstrumentation() {
  const pathname = usePathname();

  useEffect(() => {
    telemetryService.start();

    const navigation = performance.getEntriesByType("navigation")[0];
    const durationMs = navigation
      ? Math.max(0, Math.round(navigation.duration))
      : 0;
    telemetryService.track("page_load_measured", {
      page_name: pathname,
      duration_ms: durationMs,
    });

    const referrerPageName = document.referrer
      ? new URL(document.referrer).pathname
      : undefined;
    const pageViewProperties = referrerPageName
      ? { page_name: pathname, referrer_page_name: referrerPageName }
      : { page_name: pathname };
    telemetryService.track("backoffice_page_viewed", pageViewProperties);

    const handleError = () => {
      telemetryService.track("api_request_failed", {
        endpoint: "client",
        http_status: 0,
        error_code: "unhandled_error",
      });
    };
    const handleUnhandledRejection = () => {
      telemetryService.track("api_request_failed", {
        endpoint: "client",
        http_status: 0,
        error_code: "unhandled_rejection",
      });
    };

    window.addEventListener("error", handleError);
    window.addEventListener("unhandledrejection", handleUnhandledRejection);

    return () => {
      window.removeEventListener("error", handleError);
      window.removeEventListener("unhandledrejection", handleUnhandledRejection);
      telemetryService.stop();
    };
  }, [pathname]);

  return null;
}