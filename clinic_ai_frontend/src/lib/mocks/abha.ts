export async function lookupAbhaMock(abhaId: string) {
  await new Promise((resolve) => setTimeout(resolve, 350));
  const clean = abhaId.replace(/\D/g, "").slice(0, 14);
  return {
    abha_id: clean,
    name: `abha patient ${clean.slice(-4)}`,
    gender: Number(clean.slice(-1)) % 2 === 0 ? "female" : "male",
    dob: "1990-01-01",
    mobile: `9${clean.slice(0, 9)}`,
    address: "mock address, india",
  };
}
