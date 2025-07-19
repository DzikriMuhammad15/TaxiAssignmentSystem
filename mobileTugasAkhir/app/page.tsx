import App from "../App"
import { View, Text } from "react-native"
import "../global.css"

export default function Page() {
  return (
    <View className="flex-1 justify-center items-center">
      <Text className="text-xl font-bold mb-5">Taxi Driver App</Text>
      <App />
    </View>
  )
}
