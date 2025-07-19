import dynamic from "next/dynamic"
import type { Assignment, BaseState, TaxiState } from "./dashboard"

const MapContent = dynamic(() => import("./map-content"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-gray-100">
      <p>Loading map...</p>
    </div>
  ),
})

interface MapContainerProps {
  taxiStates: Record<string, TaxiState>
  baseStates: Record<string, BaseState>
}

export function MapContainer({ taxiStates, baseStates}: MapContainerProps) {
  return <MapContent taxiStates={taxiStates} baseStates={baseStates} />
}
