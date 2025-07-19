
const isBrowser = typeof window !== "undefined"



const hostname = isBrowser ? window.location.hostname : "localhost"


export const API_BASE_URL = `http://${hostname}:5010`

export const WEBSOCKET_URL = `http://${hostname}:5010`


export const DEFAULT_MAP_CENTER = [-6.9, 107.6] 
export const DEFAULT_MAP_ZOOM = 13
export const BASE_RADIUS = 500 
