import type { BookingMode, LocationSelection, RoutePoint } from "../types";

export const rideTypeOptions = ["Comfort", "Quick", "Shared", "Corporate"];

export const parcelTypeOptions = [
  "Medical Package",
  "Documents",
  "Food Package",
  "Electronics",
  "Groceries",
];

export const parcelPriorityOptions = ["Low", "Medium", "High", "Urgent"] as const;

export const bookingModes: Array<{ key: BookingMode; label: string }> = [
  { key: "ride", label: "Ride" },
  { key: "parcel", label: "Parcel" },
  { key: "captain", label: "Captain" },
];

export const defaultVelloreLocation: RoutePoint = {
  name: "VIT Service Hub",
  lat: 12.9701,
  lng: 79.1592,
};

export const supportedLocalPlaces: RoutePoint[] = [
  {
    name: "VIT Main Gate",
    lat: 12.9692,
    lng: 79.1559,
  },
  {
    name: "CMC Hospital",
    lat: 12.9259,
    lng: 79.1356,
  },
  {
    name: "Silver Jubilee Tower",
    lat: 12.9718,
    lng: 79.1634,
  },
  {
    name: "Gandhi Nagar",
    lat: 12.9448,
    lng: 79.1324,
  },
  {
    name: "Katpadi Railway Station",
    lat: 12.9682,
    lng: 79.1456,
  },
  {
    name: "Brahmapuram",
    lat: 12.9608,
    lng: 79.1774,
  },
  {
    name: "Sriram Nagar",
    lat: 12.9327,
    lng: 79.1574,
  },
  {
    name: "Kangeyanallur",
    lat: 12.9252,
    lng: 79.1707,
  },
  {
    name: "Virupakshipuram",
    lat: 12.9348,
    lng: 79.1446,
  },
  {
    name: "Thottapalayam",
    lat: 12.9077,
    lng: 79.1451,
  },
];

function normalizeLocalPlace(value: string) {
  return value.toLowerCase().replace(/-/g, " ").replace(/\s+/g, " ").trim();
}

export function findSupportedLocalPlace(value: string): RoutePoint | null {
  const normalized = normalizeLocalPlace(value);

  if (!normalized) {
    return null;
  }

  const match = supportedLocalPlaces.find(
    (place) => normalizeLocalPlace(place.name) === normalized,
  );

  return match ?? null;
}

export function searchSupportedLocalPlaces(value: string, limit = 10): RoutePoint[] {
  const normalized = normalizeLocalPlace(value);

  if (!normalized) {
    return supportedLocalPlaces.slice(0, limit);
  }

  const startsWithMatches = supportedLocalPlaces.filter((place) =>
    normalizeLocalPlace(place.name).startsWith(normalized),
  );
  const includesMatches = supportedLocalPlaces.filter((place) =>
    normalizeLocalPlace(place.name).includes(normalized),
  );

  return [...startsWithMatches, ...includesMatches.filter((place) => !startsWithMatches.includes(place))].slice(
    0,
    limit,
  );
}

export function routePointToSelection(point: RoutePoint): LocationSelection {
  return {
    name: point.name,
    lat: point.lat,
    lng: point.lng,
  };
}

export function selectionToRoutePoint(selection: LocationSelection): RoutePoint | null {
  if (!selection.name.trim()) {
    return null;
  }

  if (selection.lat === null || selection.lng === null) {
    return findSupportedLocalPlace(selection.name);
  }

  return {
    name: selection.name.trim(),
    lat: selection.lat,
    lng: selection.lng,
  };
}
