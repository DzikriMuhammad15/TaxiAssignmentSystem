"use client"

import { useState, useEffect } from "react"
import { AlertCircle, CheckCircle, WifiOff } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { API_BASE_URL } from "@/lib/config"

export function ConnectionStatus() {
  const [status, setStatus] = useState<"checking" | "connected" | "disconnected">("checking")
  const [details, setDetails] = useState("")

  const checkConnection = async () => {
    setStatus("checking")
    try {
      const response = await fetch(`${API_BASE_URL}/health`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      })

      if (response.ok) {
        setStatus("connected")
        setDetails(`Connected to ${API_BASE_URL}`)
      } else {
        setStatus("disconnected")
        setDetails(`Server responded with status: ${response.status}`)
      }
    } catch (error) {
      setStatus("disconnected")
      setDetails(`Failed to connect to ${API_BASE_URL}: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  useEffect(() => {
    checkConnection()
    const interval = setInterval(checkConnection, 30000)
    return () => clearInterval(interval)
  }, [])

  if (status === "connected") {
    return (
      <Alert className="bg-green-50 border-green-200">
        <CheckCircle className="h-4 w-4 text-green-500" />
        <AlertTitle className="text-green-700">Connected</AlertTitle>
        <AlertDescription className="text-green-600">{details}</AlertDescription>
      </Alert>
    )
  }

  if (status === "disconnected") {
    return (
      <Alert variant="destructive">
        <WifiOff className="h-4 w-4" />
        <AlertTitle>Connection Error</AlertTitle>
        <AlertDescription className="flex flex-col gap-2">
          <span>{details}</span>
          <Button size="sm" onClick={checkConnection} className="self-start">
            Retry Connection
          </Button>
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <Alert>
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Checking Connection</AlertTitle>
      <AlertDescription>Verifying connection to the backend server...</AlertDescription>
    </Alert>
  )
}
