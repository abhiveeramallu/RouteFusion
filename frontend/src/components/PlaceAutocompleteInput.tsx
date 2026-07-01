import { Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  findSupportedLocalPlace,
  routePointToSelection,
  searchSupportedLocalPlaces,
  supportedLocalPlaces,
} from "../lib/constants";
import type { LocationSelection } from "../types";

type PlaceAutocompleteInputProps = {
  label: string;
  placeholder: string;
  value: LocationSelection;
  onChange: (nextValue: LocationSelection) => void;
};

export function PlaceAutocompleteInput({
  label,
  placeholder,
  value,
  onChange,
}: PlaceAutocompleteInputProps) {
  const blurTimeoutRef = useRef<number | null>(null);
  const [isFocused, setIsFocused] = useState(false);
  const suggestions = useMemo(() => {
    const exactLocalMatch = findSupportedLocalPlace(value.name);

    if (isFocused && exactLocalMatch) {
      return supportedLocalPlaces.slice(0, 10);
    }

    return searchSupportedLocalPlaces(value.name, 10);
  }, [isFocused, value.name]);

  useEffect(() => {
    return () => {
      if (blurTimeoutRef.current) {
        window.clearTimeout(blurTimeoutRef.current);
      }
    };
  }, []);

  return (
    <label className="grid gap-2">
      <span className="text-sm font-medium text-[#4b5563]">{label}</span>
      <div className="relative">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9ca3af]" />
        <input
          value={value.name}
          placeholder={placeholder}
          onFocus={() => {
            if (blurTimeoutRef.current) {
              window.clearTimeout(blurTimeoutRef.current);
            }
            setIsFocused(true);
          }}
          onBlur={() => {
            blurTimeoutRef.current = window.setTimeout(() => {
              setIsFocused(false);
            }, 120);
          }}
          onChange={(event) =>
            (() => {
              const nextValue = event.target.value;
              const localMatch = findSupportedLocalPlace(nextValue);
              onChange({
                name: nextValue,
                lat: localMatch?.lat ?? null,
                lng: localMatch?.lng ?? null,
              });
            })()
          }
          className="w-full rounded-2xl border border-[#dbe1e7] bg-[#f9fafb] py-3 pl-11 pr-4 text-sm text-[#111827] outline-none transition placeholder:text-[#9ca3af] focus:border-[#111111] focus:bg-white"
        />
        {isFocused && suggestions.length ? (
          <div className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-20 overflow-hidden rounded-[22px] border border-[#dbe1e7] bg-white shadow-[0_24px_50px_rgba(15,23,42,0.12)]">
            <div className="border-b border-[#eef1f4] px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6b7280]">
              Suggested locations
            </div>
            <div className="max-h-64 overflow-y-auto py-1">
              {suggestions.map((place) => (
                <button
                  key={place.name}
                  type="button"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => {
                    onChange(routePointToSelection(place));
                    setIsFocused(false);
                  }}
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm text-[#111827] transition hover:bg-[#f9fafb]"
                >
                  <span className="font-medium">{place.name}</span>
                  <span className="text-xs text-[#6b7280]">Quick pick</span>
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </label>
  );
}
