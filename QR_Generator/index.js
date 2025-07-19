const QRCode = require("qrcode")
const fs = require("fs")
const path = require("path")

// Base data
const BASE_DATA = {
  12345: "d'Botanica Pasteur",
  12346: "Cihampelas Walk (Ciwalk)",
  12347: "Paris Van Java (PVJ)",
  12348: "Bandung Indah Plaza (BIP)",
  12349: "Summarecon Mall Bandung",
  12350: "Trans Studio Mall Bandung",
  12351: "Stasiun Bandung",
  12352: "Stasiun Padalarang Whoosh",
  12353: "Stasiun Tegalluar Whoosh",
  12354: "Terminal Leuwipanjang",
  12355: "Kertajati International Airport",
  12356: "Cititrans Dipatiukur",
  12357: "Shuttle Drop Off Pasteur",
  12358: "Majesty Apartement",
  12359: "Kota Baru Parahyangan",
  12360: "W Super Club",
  12361: "MOD Pool and Club",
  12362: "Dusun Bambu",
  12363: "Lembang Park Zoo",
  12364: "The Lodge Maribaya",
  12365: "Komplek Pemerintahan Kab. Bandung (Soreang)",
  12366: "Rest Area Alun-Alun Lembang",
}

async function generateSingleQR(baseId, customName = null) {
  try {
    // Check if base exists or use custom name
    const baseName = BASE_DATA[baseId] || customName || `Base ${baseId}`

    // Create output directory
    const outputDir = "./qr-codes"
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir)
    }

    // Generate filename
    const fileName = `base-${baseId}-${baseName.replace(/[^a-zA-Z0-9]/g, "-")}.png`
    const filePath = path.join(outputDir, fileName)

    // Generate QR code
    await QRCode.toFile(filePath, baseId, {
      width: 400,
      margin: 2,
      color: {
        dark: "#000000",
        light: "#FFFFFF",
      },
    })

    console.log(` QR Code Generated Successfully!`)
    console.log(` Base: ${baseName}`)
    console.log(` Base ID: ${baseId}`)
    console.log(` File: ${filePath}`)
    console.log(` QR Content: "${baseId}"`)

    return filePath
  } catch (error) {
    console.error(` Error generating QR code:`, error)
    throw error
  }
}

// Command line usage
const args = process.argv.slice(2)
if (args.length === 0) {
  console.log(`masukkan base_id di argumen pertama (seperti misalnya: node index.js 40191 (untuk membuat qr code untuk base dengan base_id: 40191))`)
} else {
  const baseId = args[0]
  const customName = args[1]
  generateSingleQR(baseId, customName)
}

module.exports = { generateSingleQR, BASE_DATA }
