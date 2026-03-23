import FindingCard from "./FindingCard.jsx";

const VULN_MODULES = ["header_probe", "path_probe", "cms_detect"];

export default function VulnSurface({ findings }) {
  const vulnFindings = findings.filter((f) => VULN_MODULES.includes(f.module));
  if (vulnFindings.length === 0) return null;

  return (
    <div className="mt-6">
      <h2
        className="text-sm font-semibold mb-3 pb-2 border-b uppercase tracking-wider"
        style={{ color: "#6b7280", borderColor: "#2a2d35" }}
      >
        Passive Vulnerability Surface
      </h2>
      {vulnFindings.map((f) => (
        <FindingCard key={f.id} finding={f} />
      ))}
    </div>
  );
}
