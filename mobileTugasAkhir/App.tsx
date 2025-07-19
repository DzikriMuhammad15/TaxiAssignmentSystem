"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import {
  View,
  Text,
  Alert,
  TouchableOpacity,
  SafeAreaView,
  ActivityIndicator,
  TextInput,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from "react-native"
import { CameraView, useCameraPermissions } from "expo-camera"
import { io, type Socket } from "socket.io-client"
import AsyncStorage from "@react-native-async-storage/async-storage"
import NetInfo from "@react-native-community/netinfo"
import { StatusBar as ExpoStatusBar } from "expo-status-bar"
import "./global.css"

const BACKEND_URL = "http://172.20.10.2:5010"

interface Assignment {
  taxi_id: string
  assigned_base: string
  polyline: string
  deviate_radius: number
  encoded_route_node_id: string
}

interface Notification {
  type: string
  base_id: string
  message: string
}

interface ConnectionState {
  connected: boolean
  reconnecting: boolean
  error: string | null
}

interface LoginForm {
  username: string
  password: string
}

interface RegisterForm {
  username: string
  name: string
  password: string
  confirmPassword: string
  taxi_id: string
}

export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [loading, setLoading] = useState(true)
  const [showCamera, setShowCamera] = useState(false)
  const [showRegister, setShowRegister] = useState(false)
  const isScanningRef = useRef(false)
  const [currentAssignment, setCurrentAssignment] = useState<Assignment | null>(null)
  const [notification, setNotification] = useState<Notification | null>(null)
  const [permission, requestPermission] = useCameraPermissions()
  const [taxiId, setTaxiId] = useState<string | null>(null)
  const [connectionState, setConnectionState] = useState<ConnectionState>({
    connected: false,
    reconnecting: false,
    error: null,
  })
  const [loginForm, setLoginForm] = useState<LoginForm>({
    username: "",
    password: "",
  })
  const [registerForm, setRegisterForm] = useState<RegisterForm>({
    username: "",
    name: "",
    password: "",
    confirmPassword: "",
    taxi_id: "",
  })
  const [authLoading, setAuthLoading] = useState(false)
  const socketRef = useRef<Socket | null>(null)

  let isAlertVisible = false

  const showAlert = (title: string, message: string, buttons: any[], onDismiss?: () => void) => {
    console.log(`isAlertVisible: ${isAlertVisible}`)
    if (isAlertVisible && (title !== "New Assignment" && title !== "Violation Notification" && title !== "cancel_assignment")) {
      return
    }

    
    isAlertVisible = true
    Alert.alert(title, message, buttons, {
      onDismiss: () => {
        isAlertVisible = false
        if (onDismiss) onDismiss()
      },
    })
  }

  useEffect(() => {
    checkLoginStatus()

    const unsubscribe = NetInfo.addEventListener((state) => {
      if (state.isConnected && socketRef.current && !socketRef.current.connected) {
        console.log("Network reconnected, attempting to reconnect WebSocket")
        connectWebSocket(taxiId!)
      }
    })

    return () => {
      unsubscribe()
      if (socketRef.current) {
        socketRef.current.disconnect()
      }
    }
  }, [])

  const checkLoginStatus = async () => {
    try {
      const token = await AsyncStorage.getItem("token")
      const storedTaxiId = await AsyncStorage.getItem("taxiId")

      if (token && storedTaxiId) {
        setTaxiId(storedTaxiId)
        setIsLoggedIn(true)
        connectWebSocket(storedTaxiId)
      }
    } catch (error) {
      console.error("Error checking login status:", error)
    } finally {
      setLoading(false)
    }
  }

  const connectWebSocket = useCallback((taxiId: string) => {
    if (socketRef.current) {
      socketRef.current.disconnect()
    }

    setConnectionState((prev) => ({ ...prev, reconnecting: true, error: null }))

    socketRef.current = io(BACKEND_URL, {
      transports: ["websocket", "polling"],
      timeout: 20000,
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    })

    socketRef.current.on("connect", () => {
      console.log("Connected to WebSocket")
      setConnectionState({ connected: true, reconnecting: false, error: null })

      socketRef.current?.emit("frontend_register", { taxi_id: taxiId })
    })

    socketRef.current.on("connect_error", (error) => {
      console.error("WebSocket connection error:", error)
      setConnectionState((prev) => ({
        ...prev,
        connected: false,
        reconnecting: false,
        error: error.message,
      }))
    })

    socketRef.current.on("disconnect", (reason) => {
      console.log("Disconnected from WebSocket:", reason)
      setConnectionState((prev) => ({ ...prev, connected: false }))
    })

    socketRef.current.on("reconnect", (attemptNumber) => {
      console.log("Reconnected to WebSocket after", attemptNumber, "attempts")
      setConnectionState({ connected: true, reconnecting: false, error: null })
    })

    socketRef.current.on("reconnect_attempt", (attemptNumber) => {
      console.log("Attempting to reconnect:", attemptNumber)
      setConnectionState((prev) => ({ ...prev, reconnecting: true }))
    })

    socketRef.current.on("reconnect_failed", () => {
      setConnectionState((prev) => ({
        ...prev,
        reconnecting: false,
        error: "Failed to reconnect to server",
      }))
    })

    socketRef.current.on("assign_base", (assignment: Assignment) => {
      console.log("Received assignment:", assignment)
      setCurrentAssignment(assignment)

      // Reset alert agar bisa tampil meskipun ada alert lain
      
      isAlertVisible = false
      showAlert(
        "New Assignment",
        `You have been assigned to base ${assignment.assigned_base}. Please proceed to the location.`,
        [{ text: "OK", onPress: () => {isAlertVisible = false} }],
      )
    })

    socketRef.current.on("notification", (notification: Notification) => {
      console.log("notification:", notification)
      setNotification(notification)

      if (notification.type === "in_base_area") {
        showAlert("Base Area Notification", notification.message, [
          { text: "Scan QR Code", onPress: () => openCamera() },
          { text: "Later", style: "cancel", onPress: () => {isAlertVisible = false}},
        ])
      }

      else if(notification.type === "violation"){
        setCurrentAssignment(null)
        showAlert("Violation Notification", notification.message, [
          { text: "OK", style: "cancel", onPress: () => {isAlertVisible = false}},
        ])
      }
      else if(notification.type === "cancel_assignment"){
        setCurrentAssignment(null)
        showAlert("Cancle Assignment Notification", notification.message, [
          { text: "OK", style: "cancel", onPress: () => {isAlertVisible = false}},
        ])
      }
    })
  }, [])

  const validateLoginForm = (): boolean => {
    if (!loginForm.username.trim()) {
      Alert.alert("Validation Error", "Please enter your username")
      return false
    }
    if (!loginForm.password.trim()) {
      Alert.alert("Validation Error", "Please enter your password")
      return false
    }
    return true
  }

  const validateRegisterForm = (): boolean => {
    if (!registerForm.username.trim()) {
      Alert.alert("Validation Error", "Please enter a username")
      return false
    }
    if (!registerForm.name.trim()) {
      Alert.alert("Validation Error", "Please enter your full name")
      return false
    }
    if (!registerForm.password.trim()) {
      Alert.alert("Validation Error", "Please enter a password")
      return false
    }
    if (registerForm.password.length < 6) {
      Alert.alert("Validation Error", "Password must be at least 6 characters long")
      return false
    }
    if (registerForm.password !== registerForm.confirmPassword) {
      Alert.alert("Validation Error", "Passwords do not match")
      return false
    }
    if (!registerForm.taxi_id.trim()) {
      Alert.alert("Validation Error", "Please enter your taxi ID")
      return false
    }
    return true
  }

  const login = async () => {
    if (!validateLoginForm()) return

    try {
      setAuthLoading(true)
      const response = await fetch(`${BACKEND_URL}/api/loginDriver`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: loginForm.username.trim(),
          password: loginForm.password,
        }),
      })

      const data = await response.json()

      if (response.ok) {
        await AsyncStorage.setItem("token", data.token)
        await AsyncStorage.setItem("userId", data.user_id)

        try {
          const userResponse = await fetch(`${BACKEND_URL}/api/getUserData`, {
            headers: {
              Authorization: `Bearer ${data.token}`,
            },
          })

          if (userResponse.ok) {
            const userData = await userResponse.json()
            const userTaxiId = userData.taxi_id

            await AsyncStorage.setItem("taxiId", userTaxiId)
            setTaxiId(userTaxiId)
            setIsLoggedIn(true)
            connectWebSocket(userTaxiId)
            
            // clear
            setLoginForm({ username: "", password: "" })
          } else {
            // Fallback
            const userTaxiId = "0"
            await AsyncStorage.setItem("taxiId", userTaxiId)
            setTaxiId(userTaxiId)
            setIsLoggedIn(true)
            connectWebSocket(userTaxiId)

            // Clear
            setLoginForm({ username: "", password: "" })
          }
        } catch (error) {
          console.error("Error getting user data:", error)
          // Fallback
          const userTaxiId = "0"
          await AsyncStorage.setItem("taxiId", userTaxiId)
          setTaxiId(userTaxiId)
          setIsLoggedIn(true)
          connectWebSocket(userTaxiId)

          // Clear login form
          setLoginForm({ username: "", password: "" })
        }
      } else {
        Alert.alert("Login Failed", data.error || "Please check your credentials")
      }
    } catch (error) {
      console.error("Login error:", error)
      Alert.alert("Login Error", "Failed to connect to server")
    } finally {
      setAuthLoading(false)
    }
  }

  const register = async () => {
    if (!validateRegisterForm()) return

    try {
      setAuthLoading(true)
      const response = await fetch(`${BACKEND_URL}/api/registerDriver`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: registerForm.username.trim(),
          name: registerForm.name.trim(),
          password: registerForm.password,
          taxi_id: registerForm.taxi_id.trim(),
        }),
      })

      const data = await response.json()

      if (response.ok) {
        Alert.alert("Registration Successful", "Your account has been created successfully. You can now log in.", [
          {
            text: "OK",
            onPress: () => {
              setShowRegister(false)
              // Clear
              setRegisterForm({
                username: "",
                name: "",
                password: "",
                confirmPassword: "",
                taxi_id: "",
              })
              // Pre-fill login
              setLoginForm((prev) => ({ ...prev, username: registerForm.username.trim() }))
            },
          },
        ])
      } else {
        Alert.alert("Registration Failed", data.error || "Failed to create account")
      }
    } catch (error) {
      console.error("Registration error:", error)
      Alert.alert("Registration Error", "Failed to connect to server")
    } finally {
      setAuthLoading(false)
    }
  }

  const openCamera = async () => {
    if (!permission) {
      return
    }

    if (!permission.granted) {
      const result = await requestPermission()
      if (!result.granted) {
        Alert.alert("Permission Required", "Camera permission is required to scan QR codes")
        return
      }
    }

    setShowCamera(true)
  }

  const handleQRCodeScanned = async ({ data }: { data: string }) => {
    if (isScanningRef.current) return

    isScanningRef.current = true
    setShowCamera(false)

    try {
      const baseId = data

      const token = await AsyncStorage.getItem("token")
      if (!token) {
        Alert.alert("Error", "Not logged in")
        return
      }

      const response = await fetch(`${BACKEND_URL}/api/checkInTaxi`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ base_id: baseId }),
      })

      const result = await response.json()

      if (response.ok) {
        Alert.alert("Success", result.message)
        setCurrentAssignment(null)
        setNotification(null)
      } else {
        Alert.alert("Check-in Failed", result.error || "Failed to check in")
      }
    } catch (error) {
      console.error("Check-in error:", error)
      Alert.alert("Error", "Failed to check in")
    } finally {
      setTimeout(() => {
        isScanningRef.current = false
      }, 4000)
    }
  }

  const logout = async () => {
    try {
      await AsyncStorage.multiRemove(["token", "userId", "taxiId"])
      if (socketRef.current) {
        socketRef.current.disconnect()
      }
      setIsLoggedIn(false)
      setTaxiId(null)
      setCurrentAssignment(null)
      setNotification(null)
      setConnectionState({ connected: false, reconnecting: false, error: null })
      // Clear form
      setLoginForm({ username: "", password: "" })
      setRegisterForm({ username: "", name: "", password: "", confirmPassword: "", taxi_id: "" })
    } catch (error) {
      console.error("Logout error:", error)
    }
  }

  const retryConnection = () => {
    if (taxiId) {
      connectWebSocket(taxiId)
    }
  }

  if (loading) {
    return (
      <SafeAreaView className="flex-1 bg-gray-100">
        <ExpoStatusBar style="dark" />
        <View className="flex-1 justify-center items-center">
          <ActivityIndicator size="large" color="#007AFF" />
          <Text className="mt-2.5 text-base text-center text-gray-600">Loading...</Text>
        </View>
      </SafeAreaView>
    )
  }

  if (showCamera) {
    return (
      <View className="flex-1">
        <ExpoStatusBar style="light" />
        <CameraView
          style={{ flex: 1 }}
          facing="back"
          onBarcodeScanned={handleQRCodeScanned}
          barcodeScannerSettings={{
            barcodeTypes: ["qr"],
          }}
        >
          <View className="flex-1 bg-transparent justify-center items-center">
            <Text className="text-lg text-white text-center mb-5 bg-black/50 p-2.5 rounded-lg">
              Scan QR Code to Check In
            </Text>
            <TouchableOpacity className="bg-white/30 px-5 py-2.5 rounded-lg" onPress={() => setShowCamera(false)}>
              <Text className="text-white text-base font-semibold">Cancel</Text>
            </TouchableOpacity>
          </View>
        </CameraView>
      </View>
    )
  }

  if (!isLoggedIn) {
    return (
      <SafeAreaView className="flex-1 bg-gray-100">
        <ExpoStatusBar style="dark" />
        <KeyboardAvoidingView className="flex-1" behavior={Platform.OS === "ios" ? "padding" : "height"}>
          <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: "center" }}>
            <View className="flex-1 justify-center p-5">
              <Text className="text-3xl font-bold mb-2.5 text-gray-800 text-center">Bluebird</Text>

              {showRegister ? (
                // Register Form
                <View className="w-full">
                  <View className="mb-5">

                    <Text className="text-base font-semibold text-gray-800 mb-2">Username</Text>
                    <TextInput
                      className="border border-gray-300 rounded-lg p-4 text-base bg-white"
                      value={registerForm.username}
                      onChangeText={(text) => setRegisterForm((prev) => ({ ...prev, username: text }))}
                      placeholder="Enter username"
                      autoCapitalize="none"
                      autoCorrect={false}
                    />
                  </View>

                  <View className="mb-5">
                    <Text className="text-base font-semibold text-gray-800 mb-2">Full Name</Text>
                    <TextInput
                      className="border border-gray-300 rounded-lg p-4 text-base bg-white"
                      value={registerForm.name}
                      onChangeText={(text) => setRegisterForm((prev) => ({ ...prev, name: text }))}
                      placeholder="Enter your full name"
                      autoCapitalize="words"
                    />
                  </View>

                  <View className="mb-5">
                    <Text className="text-base font-semibold text-gray-800 mb-2">Taxi ID</Text>
                    <TextInput
                      className="border border-gray-300 rounded-lg p-4 text-base bg-white"
                      value={registerForm.taxi_id}
                      onChangeText={(text) => setRegisterForm((prev) => ({ ...prev, taxi_id: text }))}
                      placeholder="Enter your taxi ID"
                      keyboardType="numeric"
                    />
                  </View>

                  <View className="mb-5">
                    <Text className="text-base font-semibold text-gray-800 mb-2">Password</Text>
                    <TextInput
                      className="border border-gray-300 rounded-lg p-4 text-base bg-white"
                      value={registerForm.password}
                      onChangeText={(text) => setRegisterForm((prev) => ({ ...prev, password: text }))}
                      placeholder="Enter password (min 6 characters)"
                      secureTextEntry
                      autoCapitalize="none"
                    />
                  </View>

                  <View className="mb-5">
                    <Text className="text-base font-semibold text-gray-800 mb-2">Confirm Password</Text>
                    <TextInput
                      className="border border-gray-300 rounded-lg p-4 text-base bg-white"
                      value={registerForm.confirmPassword}
                      onChangeText={(text) => setRegisterForm((prev) => ({ ...prev, confirmPassword: text }))}
                      placeholder="Confirm your password"
                      secureTextEntry
                      autoCapitalize="none"
                    />
                  </View>

                  <TouchableOpacity
                    className={`bg-blue-500 px-10 py-4 rounded-lg items-center mb-4 ${authLoading ? "opacity-60" : ""}`}
                    onPress={register}
                    disabled={authLoading}
                  >
                    {authLoading ? (
                      <ActivityIndicator color="white" />
                    ) : (
                      <Text className="text-white text-lg font-semibold">Create Account</Text>
                    )}
                  </TouchableOpacity>

                  <TouchableOpacity
                    className="py-2.5 items-center"
                    onPress={() => setShowRegister(false)}
                    disabled={authLoading}
                  >
                    <Text className="text-blue-500 text-base font-medium">Login</Text>
                  </TouchableOpacity>
                </View>
              ) : (
                // Login Form
                <View className="w-full">

                  <View className="mb-5">
                    <Text className="text-base font-semibold text-gray-800 mb-2">Username</Text>
                    <TextInput
                      className="border border-gray-300 rounded-lg p-4 text-base bg-white"
                      value={loginForm.username}
                      onChangeText={(text) => setLoginForm((prev) => ({ ...prev, username: text }))}
                      placeholder="Enter your username"
                      autoCapitalize="none"
                      autoCorrect={false}
                    />
                  </View>

                  <View className="mb-5">
                    <Text className="text-base font-semibold text-gray-800 mb-2">Password</Text>
                    <TextInput
                      className="border border-gray-300 rounded-lg p-4 text-base bg-white"
                      value={loginForm.password}
                      onChangeText={(text) => setLoginForm((prev) => ({ ...prev, password: text }))}
                      placeholder="Enter your password"
                      secureTextEntry
                      autoCapitalize="none"
                    />
                  </View>

                  <TouchableOpacity
                    className={`bg-blue-500 px-10 py-4 rounded-lg items-center mb-4 ${authLoading ? "opacity-60" : ""}`}
                    onPress={login}
                    disabled={authLoading}
                  >
                    {authLoading ? (
                      <ActivityIndicator color="white" />
                    ) : (
                      <Text className="text-white text-lg font-semibold">Login</Text>
                    )}
                  </TouchableOpacity>

                  <TouchableOpacity
                    className="py-2.5 items-center"
                    onPress={() => setShowRegister(true)}
                    disabled={authLoading}
                  >
                    <Text className="text-blue-500 text-base font-medium">Register</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    )
  }

  return (
    <SafeAreaView className="flex-1 bg-gray-100">
      <ExpoStatusBar style="dark" />

      {/* header */}
      <View className="bg-white p-5 border-b border-gray-200">
        <Text className="text-2xl font-bold text-gray-800">Taxi Driver</Text>
        <Text className="text-base text-gray-600 mt-1">Taxi ID: {taxiId}</Text>

        {/* Connection Status */}
        <View className="flex-row items-center mt-2">
          <View className={`w-2 h-2 rounded-full mr-2 ${connectionState.connected ? "bg-green-600" : "bg-red-600"}`} />
          <Text className="text-sm text-gray-600">
            {connectionState.connected
              ? "Connected"
              : connectionState.reconnecting
                ? "Reconnecting..."
                : connectionState.error
                  ? "Connection Error"
                  : "Disconnected"}
          </Text>
        </View>

        <TouchableOpacity className="absolute top-5 right-5 bg-red-500 px-4 py-2 rounded-md" onPress={logout}>
          <Text className="text-white text-sm font-semibold">Logout</Text>
        </TouchableOpacity>
      </View>

      {/* body */}
      <View className="flex-1 p-5">
        {!connectionState.connected && connectionState.error && (
          <View className="bg-red-100 p-5 rounded-xl mb-5 border border-red-200">
            <Text className="text-lg font-bold text-red-800 mb-2">Connection Error</Text>
            <Text className="text-sm text-red-800 mb-4">{connectionState.error}</Text>
            <TouchableOpacity className="bg-red-600 px-5 py-2.5 rounded-md self-start" onPress={retryConnection}>
              <Text className="text-white text-sm font-semibold">Retry Connection</Text>
            </TouchableOpacity>
          </View>
        )}

        {currentAssignment ? (
          <View className="bg-white p-5 rounded-xl mb-5 shadow-sm">
            <Text className="text-lg font-bold mb-2.5 text-gray-800">Current Assignment</Text>
            <Text className="text-base font-semibold text-blue-500 mb-1">Base: {currentAssignment.assigned_base}</Text>
            <Text className="text-sm text-gray-600">Please proceed to the assigned base location</Text>
          </View>
        ) : (
          <View className="bg-white p-5 rounded-xl mb-5 shadow-sm">
            <Text className="text-lg font-bold mb-2.5 text-gray-800">Status</Text>
            <Text className="text-base text-gray-600">Waiting for assignment...</Text>
          </View>
        )}

        <TouchableOpacity className="bg-gray-600 px-5 py-4 rounded-lg items-center mt-5" onPress={openCamera}>
          <Text className="text-white text-base font-semibold">Scan QR Code</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  )
}
