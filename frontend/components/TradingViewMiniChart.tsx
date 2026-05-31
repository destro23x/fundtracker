"use client";

import { useEffect, useRef } from "react";

interface Props {
  /** TradingView symbol, e.g. "WSE:PKN" or "NASDAQ:AAPL" */
  symbol: string;
  colorTheme?: "light" | "dark";
  height?: number;
}

export function TradingViewMiniChart({ symbol, colorTheme = "light", height = 260 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Clean up previous widget
    container.innerHTML = "";

    const script = document.createElement("script");
    script.src =
      "https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js";
    script.async = true;
    script.innerHTML = JSON.stringify({
      symbol,
      width: "100%",
      height,
      locale: "pl",
      dateRange: "12M",
      colorTheme,
      isTransparent: true,
      autosize: true,
      largeChartUrl: `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(symbol)}`,
    });

    container.appendChild(script);

    return () => {
      container.innerHTML = "";
    };
  }, [symbol, colorTheme, height]);

  return (
    <div
      className="tradingview-widget-container w-full overflow-hidden"
      ref={containerRef}
      style={{ minHeight: height }}
    >
      <div className="tradingview-widget-container__widget" />
    </div>
  );
}
