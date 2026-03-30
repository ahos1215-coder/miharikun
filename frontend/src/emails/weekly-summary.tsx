import {
  Html,
  Head,
  Body,
  Container,
  Section,
  Heading,
  Text,
  Link,
  Hr,
} from "@react-email/components";
import type { EmailRegulationItem, EmailShipSummary } from "@/lib/types";

interface WeeklySummaryEmailProps {
  dateRange: string;
  ships: EmailShipSummary[];
}

const SEVERITY_LABELS: Record<string, string> = {
  critical: "重要",
  action_required: "要対応",
  informational: "情報",
};

function severityColor(severity: string): string {
  switch (severity) {
    case "critical":
      return "#dc2626";
    case "action_required":
      return "#ea580c";
    default:
      return "#6b7280";
  }
}

function RegulationRow({ item }: { item: EmailRegulationItem }) {
  const label = SEVERITY_LABELS[item.severity] ?? item.severity;
  const color = severityColor(item.severity);

  return (
    <tr>
      <td style={{ padding: "8px 4px", borderBottom: "1px solid #e5e7eb", verticalAlign: "top" }}>
        <Link href={item.url} style={{ color: "#1d4ed8", textDecoration: "underline", fontSize: "14px" }}>
          {item.title}
        </Link>
        <br />
        <span style={{ fontSize: "12px", color: "#6b7280" }}>{item.reason}</span>
      </td>
      <td style={{ padding: "8px 4px", borderBottom: "1px solid #e5e7eb", textAlign: "center", verticalAlign: "top", whiteSpace: "nowrap" }}>
        <span style={{ color, fontWeight: "bold", fontSize: "12px" }}>[{label}]</span>
      </td>
      <td style={{ padding: "8px 4px", borderBottom: "1px solid #e5e7eb", textAlign: "center", verticalAlign: "top", whiteSpace: "nowrap", fontSize: "12px" }}>
        {item.confidence}%
      </td>
    </tr>
  );
}

function ShipSection({ ship }: { ship: EmailShipSummary }) {
  return (
    <Section style={{ marginBottom: "24px" }}>
      <Heading as="h2" style={{ fontSize: "16px", margin: "0 0 4px 0", color: "#111827" }}>
        {ship.shipName}
      </Heading>
      <Text style={{ fontSize: "12px", color: "#6b7280", margin: "0 0 12px 0" }}>
        {ship.shipType} / {ship.grossTonnage.toLocaleString()} GT
      </Text>

      {ship.regulations.length === 0 ? (
        <Text style={{ fontSize: "14px", color: "#6b7280" }}>
          該当する規制情報はありませんでした。
        </Text>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", padding: "4px", fontSize: "12px", color: "#6b7280", borderBottom: "2px solid #d1d5db" }}>
                規制
              </th>
              <th style={{ textAlign: "center", padding: "4px", fontSize: "12px", color: "#6b7280", borderBottom: "2px solid #d1d5db" }}>
                重要度
              </th>
              <th style={{ textAlign: "center", padding: "4px", fontSize: "12px", color: "#6b7280", borderBottom: "2px solid #d1d5db" }}>
                確信度
              </th>
            </tr>
          </thead>
          <tbody>
            {ship.regulations.map((reg, i) => (
              <RegulationRow key={i} item={reg} />
            ))}
          </tbody>
        </table>
      )}
    </Section>
  );
}

export default function WeeklySummaryEmail({ dateRange, ships }: WeeklySummaryEmailProps) {
  const totalRegulations = ships.reduce((sum, s) => sum + s.regulations.length, 0);

  return (
    <Html lang="ja">
      <Head />
      <Body style={{ backgroundColor: "#f9fafb", fontFamily: "sans-serif", margin: "0", padding: "0" }}>
        <Container style={{ maxWidth: "600px", margin: "0 auto", padding: "16px" }}>
          {/* Header */}
          <Section style={{ backgroundColor: "#1e3a5f", padding: "16px 20px", borderRadius: "4px 4px 0 0" }}>
            <Heading as="h1" style={{ color: "#ffffff", fontSize: "18px", margin: "0" }}>
              MIHARIKUN 週次サマリー
            </Heading>
            <Text style={{ color: "#93c5fd", fontSize: "13px", margin: "4px 0 0 0" }}>
              {dateRange}
            </Text>
          </Section>

          {/* Summary line */}
          <Section style={{ backgroundColor: "#ffffff", padding: "16px 20px", borderBottom: "1px solid #e5e7eb" }}>
            <Text style={{ fontSize: "14px", margin: "0", color: "#374151" }}>
              登録船舶 {ships.length} 隻に対し、{totalRegulations} 件の関連規制が見つかりました。
            </Text>
          </Section>

          {/* Ship sections */}
          <Section style={{ backgroundColor: "#ffffff", padding: "16px 20px" }}>
            {ships.map((ship, i) => (
              <div key={i}>
                {i > 0 && <Hr style={{ borderColor: "#e5e7eb", margin: "16px 0" }} />}
                <ShipSection ship={ship} />
              </div>
            ))}
          </Section>

          {/* Footer */}
          <Section style={{ padding: "12px 20px", backgroundColor: "#f3f4f6", borderRadius: "0 0 4px 4px" }}>
            <Text style={{ fontSize: "11px", color: "#9ca3af", margin: "0", lineHeight: "1.5" }}>
              本サービスはAIによる参考情報の提供を目的としており、公式文書の代替ではありません。
              法令遵守の最終判断は、必ず原文を確認の上ご自身の責任で行ってください。
            </Text>
            <Text style={{ fontSize: "11px", color: "#9ca3af", margin: "4px 0 0 0" }}>
              &copy; 2026 MIHARIKUN
            </Text>
          </Section>
        </Container>
      </Body>
    </Html>
  );
}
