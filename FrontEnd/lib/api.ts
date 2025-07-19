import { API_BASE_URL} from "./config"

export async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = endpoint.startsWith("http") ? endpoint : `${API_BASE_URL}${endpoint}`

  if (!options.headers) {
    options.headers = {
      "Content-Type": "application/json",
    }
  }

  const token = localStorage.getItem("token")
  if (token && options.headers) {
    ;(options.headers as Record<string, string>)["Authorization"] = `Bearer ${token}`
  }

  options.credentials = "include"

  try {
    const response = await fetch(url, options)

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error)
    }
    return await response.json()
  } catch (error) {
    console.error("API request failed:", error)
    if (error instanceof TypeError && error.message.includes("Failed to fetch")) {
      throw new Error(`Could not connect to ${url}`)
    }
    throw error
  }
}
