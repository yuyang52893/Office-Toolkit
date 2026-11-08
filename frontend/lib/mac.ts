import type { QrDecodedMac } from "@/lib/types";

const separatorPattern = /[:.\-\s]/g;
const compactPattern = /^[0-9a-fA-F]{12}$/;

export function normalizeMac(value: string): QrDecodedMac | null {
  const compact = value.trim().replace(separatorPattern, "");
  if (!compactPattern.test(compact)) {
    return null;
  }
  const normalized = compact.toUpperCase();
  const octets = normalized.match(/.{2}/g);
  if (!octets) {
    return null;
  }
  const firstOctet = Number.parseInt(octets[0], 16);
  return {
    canonical: octets.join(":"),
    hyphenated: octets.join("-"),
    plain: normalized,
    cisco: `${octets.slice(0, 2).join("")}.${octets.slice(2, 4).join("")}.${octets
      .slice(4, 6)
      .join("")}`,
    multicast: Boolean(firstOctet & 0x01),
    locally_administered: Boolean(firstOctet & 0x02),
  };
}

