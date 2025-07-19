"use client"

import { useEffect, useRef, useState } from "react"
import L from "leaflet"
import "leaflet/dist/leaflet.css"
import type { BaseState, TaxiState } from "./dashboard"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

if (typeof window !== "undefined") {
  L.Polyline.fromEncoded = (encoded: string, options?: L.PolylineOptions) => {
    const points: [number, number][] = []
    let index = 0
    const len = encoded.length
    let lat = 0
    let lng = 0

    while (index < len) {
      let b
      let shift = 0
      let result = 0
      do {
        b = encoded.charCodeAt(index++) - 63
        result |= (b & 0x1f) << shift
        shift += 5
      } while (b >= 0x20)
      const dlat = (result & 1) !== 0 ? ~(result >> 1) : result >> 1
      lat += dlat

      shift = 0
      result = 0
      do {
        b = encoded.charCodeAt(index++) - 63
        result |= (b & 0x1f) << shift
        shift += 5
      } while (b >= 0x20)
      const dlng = (result & 1) !== 0 ? ~(result >> 1) : result >> 1
      lng += dlng

      points.push([lat * 1e-5, lng * 1e-5])
    }

    return new L.Polyline(points, options || {})
  }
}

interface MapContentProps {
  taxiStates: Record<string, TaxiState>
  baseStates: Record<string, BaseState>
}

export default function MapContent({ taxiStates, baseStates}: MapContentProps) {
  const mapRef = useRef<HTMLDivElement>(null)
  const leafletMapRef = useRef<L.Map | null>(null)
  const markersRef = useRef<Record<string, L.Marker>>({})
  const baseMarkersRef = useRef<Record<string, L.Circle>>({})
  const baseIconMarkersRef = useRef<Record<string, L.Marker>>({})
  const polylineRef = useRef<Record<string, L.Polyline>>({})
  const deviationBufferRef = useRef<Record<string, L.Polygon>>({})

  const [mapInitialized, setMapInitialized] = useState(false)
  const [selectedTaxi, setSelectedTaxi] = useState<string | null>(null)

  useEffect(() => {
    if (!mapRef.current || leafletMapRef.current) return

    const map = L.map(mapRef.current).setView([-6.9, 107.6], 13)

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map)

    leafletMapRef.current = map
    setMapInitialized(true)

    // cleanup unmount komponen
    return () => {
      map.remove()
      leafletMapRef.current = null
    }
  }, [])

  // Update taxi markers
  useEffect(() => {
    if (!mapInitialized || !leafletMapRef.current) return

    const map = leafletMapRef.current

    Object.entries(taxiStates).forEach(([taxiId, state]) => {
      const { latitude, longitude, taxi_state } = state

      if (!latitude || !longitude) return

      let markerColor = "green"
      if (taxi_state === "menuju penumpang") {
        markerColor = "yellow"
      } else if (taxi_state === "bersama penumpang") {
        markerColor = "red"
      }

      // icon
      const taxiIcon = L.divIcon({
        className: "custom-taxi-marker",
        html: `<div style="background-color: ${markerColor}; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white;"></div>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8],
      })

      // updata atau tambahkan marker
      if (markersRef.current[taxiId]) {
        markersRef.current[taxiId].setLatLng([latitude, longitude])
        markersRef.current[taxiId].setIcon(taxiIcon)
      } else {
        const marker = L.marker([latitude, longitude], { icon: taxiIcon })
          .addTo(map)
          .on("click", () => {
            setSelectedTaxi(selectedTaxi === taxiId ? null : taxiId)
          })

        markersRef.current[taxiId] = marker
      }

      const popupContent = `
        <div class="taxi-popup">
          <h3 class="font-bold">Taxi ID: ${taxiId}</h3>
          <p>Status: ${taxi_state}</p>
          <p>Battery: ${state.battery}%</p>
          <p>Location: ${latitude.toFixed(6)}, ${longitude.toFixed(6)}</p>
        </div>
      `

      markersRef.current[taxiId].bindPopup(popupContent)
    })

    Object.keys(markersRef.current).forEach((taxiId) => {
      if (!taxiStates[taxiId]) {
        map.removeLayer(markersRef.current[taxiId])
        delete markersRef.current[taxiId]
      }
    })
  }, [taxiStates, mapInitialized, selectedTaxi])

  // Update base
  useEffect(() => {
    if (!mapInitialized || !leafletMapRef.current) return

    const map = leafletMapRef.current

    Object.entries(baseStates).forEach(([baseId, state]) => {
      const { latitude, longitude, fleet } = state

      if (!latitude || !longitude) return

      const occupiedSlots = fleet.filter((slot) => slot !== null).length
      const totalSlots = fleet.length

      // icon
      const baseIcon = L.divIcon({
        className: "custom-base-marker",
        html: `<div style="background-color: #3b82f6; color: white; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid white;">${occupiedSlots}/${totalSlots}</div>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      })

      // tambahkan atau modifikasi base radius
      if (baseMarkersRef.current[baseId]) {
        baseMarkersRef.current[baseId].setLatLng([latitude, longitude])
      } else {
        console.log("latitude:", latitude, "longitude:", longitude)
        const circle = L.circle([latitude, longitude], {
          color: "blue",
          fillColor: "#3b82f6",
          fillOpacity: 0.2,
          radius: 500,
        }).addTo(map)


        baseMarkersRef.current[baseId] = circle
      }

      // tambahkan atau update marker
      if (baseIconMarkersRef.current[baseId]) {
        baseIconMarkersRef.current[baseId].setLatLng([latitude, longitude])
        baseIconMarkersRef.current[baseId].setIcon(baseIcon)
      } else {
        const marker = L.marker([latitude, longitude], { icon: baseIcon }).addTo(map)
        baseIconMarkersRef.current[baseId] = marker
      }

      // informasi fleet
      const fleetInfo = fleet
        .map((taxiId, index) => {
          if (taxiId === null) {
            return `<li>Slot ${index + 1}: Empty</li>`
          } else {
            const taxi = taxiStates[taxiId]
            const status = taxi ? taxi.taxi_state : "Unknown"
            const battery = taxi ? `${taxi.battery}%` : "Unknown"
            return `<li>Slot ${index + 1}: Taxi ${taxiId} (${status}, Battery: ${battery})</li>`
          }
        })
        .join("")

      const popupContent = `
        <div class="base-popup">
          <h3 class="font-bold">Base ID: ${baseId}</h3>
          <p>Location: ${latitude.toFixed(6)}, ${longitude.toFixed(6)}</p>
          <p>Capacity: ${occupiedSlots}/${totalSlots}</p>
          <h4 class="font-semibold mt-2">Fleet:</h4>
          <ul class="list-disc pl-5">
            ${fleetInfo}
          </ul>
        </div>
      `

      baseIconMarkersRef.current[baseId].bindPopup(popupContent)
    })

    // hapus base radius yang tidak ada
    Object.keys(baseMarkersRef.current).forEach((baseId) => {
      if (!baseStates[baseId]) {
        map.removeLayer(baseMarkersRef.current[baseId])
        delete baseMarkersRef.current[baseId]
      }
    })

    // hapus base marker yang tidak ada
    Object.keys(baseIconMarkersRef.current).forEach((baseId) => {
      if (!baseStates[baseId]) {
        map.removeLayer(baseIconMarkersRef.current[baseId])
        delete baseIconMarkersRef.current[baseId]
      }
    })
  }, [baseStates, taxiStates, mapInitialized])


  return (
    <div className="relative h-full">
      <div ref={mapRef} className="w-full h-full" />
    </div>
  )
}
