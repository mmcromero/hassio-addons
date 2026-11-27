export type RegistrationOrderItem = {
  fullName: string;
  markerStatus: string;
};

/**
 * Keeps registered repositories at the top and sorts each group by full name.
 * The input is never mutated.
 */
export function orderRegisteredRepositories<T extends RegistrationOrderItem>(repositories: readonly T[]): T[] {
  return [...repositories].sort((a, b) => {
    const registeredOrder = Number(b.markerStatus === "registered") - Number(a.markerStatus === "registered");
    return registeredOrder || a.fullName.localeCompare(b.fullName);
  });
}
