// @ts-check
// Dependency audit gate: runs `npm audit --json` and fails on any high or critical
// advisory that is not explicitly accepted in `audit-allowlist.json`.
//
// The allowlist is deliberately strict: every entry needs a reason and a review date,
// an expired entry fails the gate, and an entry that no longer matches any reported
// advisory fails too, so accepted risk cannot outlive its justification.

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";

/** Severities that block the gate, matching `npm audit --audit-level=high`. */
export const BLOCKING_SEVERITIES = new Set(["high", "critical"]);

const GHSA_PATTERN = /^GHSA(-[23456789cfghjmpqrvwx]{4}){3}$/;
const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

/**
 * @typedef {{ id: string, package: string, reason: string, reviewBy: string }} AllowlistEntry
 * @typedef {{ id: string, package: string, title: string, severity: string, url: string }} Advisory
 * @typedef {{
 *   blocking: Advisory[],
 *   accepted: Advisory[],
 *   nonBlocking: Advisory[],
 *   expired: AllowlistEntry[],
 *   stale: AllowlistEntry[],
 * }} AuditOutcome
 */

/**
 * Validates the parsed allowlist file and returns its entries.
 * @param {unknown} raw
 * @returns {AllowlistEntry[]}
 */
export function parseAllowlist(raw) {
  if (typeof raw !== "object" || raw === null || !Array.isArray(Reflect.get(raw, "advisories"))) {
    throw new Error('audit allowlist must be an object with an "advisories" array');
  }
  /** @type {unknown[]} */
  const entries = Reflect.get(raw, "advisories");
  const seen = new Set();
  return entries.map((entry, index) => {
    const where = `audit allowlist entry ${index}`;
    if (typeof entry !== "object" || entry === null) {
      throw new Error(`${where} must be an object`);
    }
    const id = Reflect.get(entry, "id");
    const pkg = Reflect.get(entry, "package");
    const reason = Reflect.get(entry, "reason");
    const reviewBy = Reflect.get(entry, "reviewBy");
    if (typeof id !== "string" || !GHSA_PATTERN.test(id)) {
      throw new Error(`${where}: "id" must be a GHSA identifier`);
    }
    if (seen.has(id)) {
      throw new Error(`${where}: duplicate id ${id}`);
    }
    seen.add(id);
    if (typeof pkg !== "string" || pkg.trim() === "") {
      throw new Error(`${where}: "package" is required`);
    }
    if (typeof reason !== "string" || reason.trim() === "") {
      throw new Error(`${where}: "reason" is required`);
    }
    if (
      typeof reviewBy !== "string" ||
      !ISO_DATE_PATTERN.test(reviewBy) ||
      Number.isNaN(Date.parse(reviewBy))
    ) {
      throw new Error(`${where}: "reviewBy" must be a YYYY-MM-DD date`);
    }
    return { id, package: pkg, reason, reviewBy };
  });
}

/**
 * Extracts the distinct source advisories from an `npm audit --json` report.
 * Transitive entries (string `via` references) repeat a source advisory and are skipped.
 * @param {unknown} report
 * @returns {Advisory[]}
 */
export function collectAdvisories(report) {
  if (typeof report !== "object" || report === null) {
    throw new Error("npm audit did not return a JSON object");
  }
  const error = Reflect.get(report, "error");
  if (error !== undefined) {
    throw new Error(`npm audit failed: ${JSON.stringify(error)}`);
  }
  const vulnerabilities = Reflect.get(report, "vulnerabilities");
  if (typeof vulnerabilities !== "object" || vulnerabilities === null) {
    throw new Error('npm audit report has no "vulnerabilities" object');
  }
  /** @type {Map<string, Advisory>} */
  const advisories = new Map();
  for (const vulnerability of Object.values(vulnerabilities)) {
    const via = Reflect.get(vulnerability, "via");
    if (!Array.isArray(via)) {
      throw new Error('npm audit vulnerability has no "via" array');
    }
    for (const source of via) {
      if (typeof source !== "object" || source === null) {
        continue;
      }
      const url = String(Reflect.get(source, "url") ?? "");
      const id = url.split("/").pop() ?? "";
      const key = id || url;
      if (!advisories.has(key)) {
        advisories.set(key, {
          id,
          package: String(Reflect.get(source, "name") ?? ""),
          title: String(Reflect.get(source, "title") ?? ""),
          severity: String(Reflect.get(source, "severity") ?? ""),
          url,
        });
      }
    }
  }
  return [...advisories.values()];
}

/**
 * Applies the allowlist to the reported advisories.
 * @param {Advisory[]} advisories
 * @param {AllowlistEntry[]} allowlist
 * @param {string} today ISO date (YYYY-MM-DD)
 * @returns {AuditOutcome}
 */
export function evaluate(advisories, allowlist, today) {
  const allowed = new Map(allowlist.map((entry) => [entry.id, entry]));
  /** @type {AuditOutcome} */
  const outcome = { blocking: [], accepted: [], nonBlocking: [], expired: [], stale: [] };
  for (const advisory of advisories) {
    if (!BLOCKING_SEVERITIES.has(advisory.severity)) {
      outcome.nonBlocking.push(advisory);
    } else if (allowed.has(advisory.id)) {
      outcome.accepted.push(advisory);
    } else {
      outcome.blocking.push(advisory);
    }
  }
  const reportedIds = new Set(advisories.map((advisory) => advisory.id));
  for (const entry of allowlist) {
    if (entry.reviewBy < today) {
      outcome.expired.push(entry);
    }
    if (!reportedIds.has(entry.id)) {
      outcome.stale.push(entry);
    }
  }
  return outcome;
}

/**
 * @param {AuditOutcome} outcome
 * @returns {boolean}
 */
export function passes(outcome) {
  return (
    outcome.blocking.length === 0 && outcome.expired.length === 0 && outcome.stale.length === 0
  );
}

/** @param {Advisory} advisory */
function describe(advisory) {
  return `${advisory.severity} ${advisory.package}: ${advisory.title} (${advisory.url})`;
}

function main() {
  const allowlistPath = fileURLToPath(new URL("../audit-allowlist.json", import.meta.url));
  const allowlist = parseAllowlist(JSON.parse(readFileSync(allowlistPath, "utf8")));

  // npm audit exits non-zero whenever it finds anything, so its JSON is the signal.
  const result = spawnSync("npm", ["audit", "--json"], {
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
  });
  if (result.error) {
    throw result.error;
  }
  const outcome = evaluate(
    collectAdvisories(JSON.parse(result.stdout)),
    allowlist,
    new Date().toISOString().slice(0, 10),
  );

  for (const advisory of outcome.nonBlocking) console.log(`note      ${describe(advisory)}`);
  for (const advisory of outcome.accepted) console.log(`accepted  ${describe(advisory)}`);
  for (const advisory of outcome.blocking) console.error(`BLOCKING  ${describe(advisory)}`);
  for (const entry of outcome.expired) {
    console.error(
      `EXPIRED   ${entry.id} (${entry.package}) was due for review on ${entry.reviewBy}`,
    );
  }
  for (const entry of outcome.stale) {
    console.error(`STALE     ${entry.id} (${entry.package}) is no longer reported; remove it`);
  }

  if (!passes(outcome)) {
    console.error("Dependency audit failed. See audit-allowlist.json to review accepted risk.");
    process.exit(1);
  }
  console.log(
    `Dependency audit passed: ${outcome.accepted.length} accepted, ${outcome.nonBlocking.length} below high.`,
  );
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
