import { Shield } from "lucide-react";

interface ComplianceGaugeProps {
  shipName: string;
  shipType: string;
  grossTonnage: number;
  applicableCount: number;
  totalCount: number;
  potentialCount: number;
}

export function ComplianceGauge({
  shipName,
  shipType,
  grossTonnage,
  applicableCount,
  totalCount,
  potentialCount,
}: ComplianceGaugeProps) {
  const rate = totalCount > 0 ? Math.round((applicableCount / totalCount) * 100) : 0;
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (rate / 100) * circumference;

  const gaugeColor =
    rate >= 80
      ? "#06b6d4" // cyan
      : rate >= 50
        ? "#f59e0b" // amber
        : "#f43f5e"; // rose

  return (
    <div
      className="glass rounded-2xl p-6 glow-cyan motion-preset-slide-up motion-duration-500"
    >
      <div className="flex items-center gap-6">
        {/* SVG Gauge */}
        <div className="relative shrink-0">
          <svg width="128" height="128" viewBox="0 0 128 128">
            {/* Background ring */}
            <circle
              cx="64"
              cy="64"
              r={radius}
              fill="none"
              stroke="rgba(255,255,255,0.06)"
              strokeWidth="8"
            />
            {/* Progress ring */}
            <circle
              cx="64"
              cy="64"
              r={radius}
              fill="none"
              stroke={gaugeColor}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              transform="rotate(-90 64 64)"
              className="animate-gauge-fill"
              style={{
                filter: `drop-shadow(0 0 8px ${gaugeColor}50)`,
                transition: "stroke-dashoffset 1.5s cubic-bezier(0.4, 0, 0.2, 1)",
              }}
            />
          </svg>
          {/* Center text */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span
              className="text-2xl font-bold tabular-nums motion-preset-fade motion-duration-500"
              style={{ color: gaugeColor }}
            >
              {rate}%
            </span>
            <span className="text-[10px] text-zinc-400 dark:text-zinc-500">
              カバー率
            </span>
          </div>
        </div>

        {/* Ship info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Shield size={16} className="text-accent-cyan shrink-0" />
            <h2 className="text-lg font-semibold truncate dark:text-white">
              {shipName}
            </h2>
          </div>
          <p className="text-sm text-zinc-400 dark:text-zinc-500 mb-3">
            {shipType} / {grossTonnage.toLocaleString()} GT
          </p>

          {/* Stats row */}
          <div className="flex gap-4">
            <div>
              <p className="text-xs text-zinc-500">該当</p>
              <p className="text-lg font-bold text-cyan-400 tabular-nums">
                {applicableCount}
              </p>
            </div>
            {potentialCount > 0 && (
              <div>
                <p className="text-xs text-zinc-500">確認待ち</p>
                <p className="text-lg font-bold text-amber-400 tabular-nums">
                  {potentialCount}
                </p>
              </div>
            )}
            <div>
              <p className="text-xs text-zinc-500">全件</p>
              <p className="text-lg font-bold text-zinc-400 tabular-nums">
                {totalCount}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
