import { useJsApiLoader, type Libraries } from "@react-google-maps/api";
import { useEffect, useState } from "react";

import { findSupportedLocalPlace } from "./constants";
import type { LocationSelection, RoutePoint } from "../types";

export const googleMapsLibraries: Libraries = [];
const googleAuthFailureEventName = "routefusion:google-auth-failure";
const googleMapsSetupGuidance =
  "Google Maps is used only for the route background and road rendering. Location selection stays on the built-in VIT-area picker.";
let authFailureBridgeInstalled = false;

declare global {
  interface Window {
    gm_authFailure?: () => void;
  }
}

function installGoogleAuthFailureBridge() {
  if (typeof window === "undefined" || authFailureBridgeInstalled) {
    return;
  }

  window.gm_authFailure = () => {
    window.dispatchEvent(new Event(googleAuthFailureEventName));
  };
  authFailureBridgeInstalled = true;
}

function isGoogleMapsEnabled() {
  return import.meta.env.VITE_ENABLE_GOOGLE_MAPS !== "false";
}

export function hasGoogleMapsApiKey() {
  return Boolean(import.meta.env.VITE_GOOGLE_MAPS_API_KEY) && isGoogleMapsEnabled();
}

export function googleMapsSetupMessage() {
  return googleMapsSetupGuidance;
}

export function freeServiceModeMessage() {
  return "Safe fallback mode is active. RouteFusion is using built-in VIT-area locations and straight-line route previews without Google billing.";
}

export function useGoogleMapsLoader() {
  const googleMapsApiKey = hasGoogleMapsApiKey()
    ? import.meta.env.VITE_GOOGLE_MAPS_API_KEY ?? ""
    : "";
  const { isLoaded, loadError } = useJsApiLoader({
    id: "routefusion-google-map",
    googleMapsApiKey,
    libraries: googleMapsLibraries,
  });
  const [authFailure, setAuthFailure] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    installGoogleAuthFailureBridge();
    const handleAuthFailure = () => setAuthFailure(true);
    window.addEventListener(googleAuthFailureEventName, handleAuthFailure);
    return () => window.removeEventListener(googleAuthFailureEventName, handleAuthFailure);
  }, []);

  useEffect(() => {
    if (!googleMapsApiKey) {
      setAuthFailure(false);
    }
  }, [googleMapsApiKey]);

  const statusMessage = !googleMapsApiKey
    ? null
    : loadError
      ? `Google Maps failed to load${loadError.message ? `: ${loadError.message}` : "."}`
      : authFailure
        ? "Google Maps rejected this browser key."
        : null;

  return {
    googleMapsApiKey,
    hasApiKey: Boolean(googleMapsApiKey),
    isLoaded,
    isReady: Boolean(googleMapsApiKey) && isLoaded && !loadError && !authFailure,
    loadError,
    authFailure,
    statusMessage,
  };
}

export async function geocodeSelection(selection: LocationSelection): Promise<LocationSelection> {
  if (!selection.name.trim()) {
    return selection;
  }

  if (selection.lat !== null && selection.lng !== null) {
    return selection;
  }

  const localLocation = findSupportedLocalPlace(selection.name);
  if (localLocation) {
    return {
      name: localLocation.name,
      lat: localLocation.lat,
      lng: localLocation.lng,
    };
  }

  if (typeof google === "undefined" || !google.maps?.Geocoder) {
    return selection;
  }

  const geocoder = new google.maps.Geocoder();
  const response = await geocoder.geocode({ address: selection.name });
  const firstResult = response.results?.[0];
  const geometry = firstResult?.geometry?.location;

  if (!firstResult || !geometry) {
    return selection;
  }

  return {
    name: firstResult.formatted_address || selection.name,
    lat: geometry.lat(),
    lng: geometry.lng(),
  };
}

export function selectionToPayloadPoint(selection: LocationSelection): RoutePoint | null {
  if (!selection.name.trim()) {
    return null;
  }

  if (selection.lat === null || selection.lng === null) {
    const localLocation = findSupportedLocalPlace(selection.name);
    return localLocation
      ? {
          name: localLocation.name,
          lat: localLocation.lat,
          lng: localLocation.lng,
        }
      : null;
  }

  return {
    name: selection.name.trim(),
    lat: selection.lat,
    lng: selection.lng,
  };
}
