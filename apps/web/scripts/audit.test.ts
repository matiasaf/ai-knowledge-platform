// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { collectAdvisories, evaluate, parseAllowlist, passes } from "./audit.mjs";

const PICOMATCH = {
  name: "picomatch",
  title: "picomatch vulnerable to ReDoS through single-branch repeated extglobs",
  url: "https://github.com/advisories/GHSA-fc5q-39xc-vjpf",
  severity: "high",
};

function report(...sources: Array<Record<string, string>>) {
  return {
    auditReportVersion: 2,
    vulnerabilities: {
      ...Object.fromEntries(sources.map((source) => [source.name, { via: [source] }])),
      // A transitive entry only references its source advisory by package name.
      vitest: { via: ["picomatch"] },
    },
  };
}

const allowPicomatch = parseAllowlist({
  advisories: [
    {
      id: "GHSA-fc5q-39xc-vjpf",
      package: "picomatch",
      reason: "dev-only tooling",
      reviewBy: "2026-12-17",
    },
  ],
});

describe("collectAdvisories", () => {
  it("returns each source advisory once and skips transitive references", () => {
    const advisories = collectAdvisories(report(PICOMATCH));
    expect(advisories).toEqual([
      {
        id: "GHSA-fc5q-39xc-vjpf",
        package: "picomatch",
        title: PICOMATCH.title,
        severity: "high",
        url: PICOMATCH.url,
      },
    ]);
  });

  it("refuses an npm error payload instead of treating it as a clean audit", () => {
    expect(() => collectAdvisories({ error: { code: "ENOTFOUND" } })).toThrow(/npm audit failed/);
    expect(() => collectAdvisories({})).toThrow(/no "vulnerabilities"/);
  });
});

describe("evaluate", () => {
  it("accepts an allowlisted high advisory before its review date", () => {
    const outcome = evaluate(collectAdvisories(report(PICOMATCH)), allowPicomatch, "2026-11-17");
    expect(outcome.accepted).toHaveLength(1);
    expect(passes(outcome)).toBe(true);
  });

  it("blocks a high advisory that is not allowlisted", () => {
    const other = {
      ...PICOMATCH,
      name: "other",
      url: "https://github.com/advisories/GHSA-2222-3333-4444",
    };
    const outcome = evaluate(
      collectAdvisories(report(PICOMATCH, other)),
      allowPicomatch,
      "2026-11-17",
    );
    expect(outcome.blocking.map((advisory) => advisory.package)).toEqual(["other"]);
    expect(passes(outcome)).toBe(false);
  });

  it("reports moderate advisories without blocking", () => {
    const moderate = { ...PICOMATCH, severity: "moderate" };
    const outcome = evaluate(collectAdvisories(report(moderate)), [], "2026-11-17");
    expect(outcome.nonBlocking).toHaveLength(1);
    expect(passes(outcome)).toBe(true);
  });

  it("fails once an allowlist entry is past its review date", () => {
    const outcome = evaluate(collectAdvisories(report(PICOMATCH)), allowPicomatch, "2026-12-18");
    expect(outcome.expired.map((entry) => entry.id)).toEqual(["GHSA-fc5q-39xc-vjpf"]);
    expect(passes(outcome)).toBe(false);
  });

  it("fails when an allowlist entry no longer matches any reported advisory", () => {
    const outcome = evaluate([], allowPicomatch, "2026-11-17");
    expect(outcome.stale.map((entry) => entry.id)).toEqual(["GHSA-fc5q-39xc-vjpf"]);
    expect(passes(outcome)).toBe(false);
  });
});

describe("parseAllowlist", () => {
  const valid = {
    id: "GHSA-fc5q-39xc-vjpf",
    package: "picomatch",
    reason: "r",
    reviewBy: "2026-12-17",
  };

  it("rejects entries without a reason, a valid id or a review date", () => {
    expect(() => parseAllowlist({ advisories: [{ ...valid, reason: " " }] })).toThrow(/reason/);
    expect(() => parseAllowlist({ advisories: [{ ...valid, id: "CVE-2026-1" }] })).toThrow(/GHSA/);
    expect(() => parseAllowlist({ advisories: [{ ...valid, reviewBy: "soon" }] })).toThrow(
      /reviewBy/,
    );
    expect(() => parseAllowlist({ advisories: [valid, valid] })).toThrow(/duplicate/);
    expect(() => parseAllowlist([])).toThrow(/advisories/);
  });

  it("accepts the checked-in allowlist", () => {
    const raw = JSON.parse(
      readFileSync(new URL("../audit-allowlist.json", import.meta.url), "utf8"),
    );
    expect(parseAllowlist(raw).length).toBeGreaterThan(0);
  });
});
