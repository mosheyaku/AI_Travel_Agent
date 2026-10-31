export interface AccommodationSuggestion {
    place_id: string;
    name: string;
    address: string;
    latitude: number;
    longitude: number;
}

export async function searchAccommodations(
    query: string,
    destination: string,
    signal?: AbortSignal
): Promise<AccommodationSuggestion[]> {
    const params = new URLSearchParams({ query, destination });

    const response = await fetch(
        `/api/places/accommodations?${params.toString()}`,
        { signal }
    );

    if (!response.ok) {
        throw new Error("Failed to search accommodations.");
    }

    return (await response.json()) as AccommodationSuggestion[];
}