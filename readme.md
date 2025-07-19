# EV Taxi Assignment System

## System Overview

The EV Taxi Assignment System consists of three main components:

- **Client-side Mobile Application** - For taxi drivers
- **Client-side Web Application** - For field operators  
- **Server-side Infrastructure** - Backend services and databases

## Server Architecture

The server-side infrastructure runs on Docker containers with the following services:

| Container Name | Description |
|----------------|-------------|
| order-rate-backend-simulation | Simulates functionality for retrieving order rates in marking areas |
| osrm-prep | Prepares the OSRM server environment |
| gmaps-backend-simulation | Simulates Google Maps API functionality for duration and distance matrix services |
| mosquitto | MQTT broker server |
| postgres-db | PostgreSQL database server |
| order-rate-backend-simulation-60-bases | Order rate simulation server for 60-base study case |
| osrm | Open Source Routing Machine server |
| pgadmin | PostgreSQL database administration and analysis tool |
| backend-ta | Main backend server for the EV Taxi Assignment System |

## Initial Setup

### Clone the Repository

\`\`\`bash
git clone https://github.com/DzikriMuhammad15/TaxiAssignmentSystem.git
\`\`\`

### Create Python Virtual Environment

\`\`\`bash
python -m venv .venv
\`\`\`

### Activate Virtual Environment

\`\`\`bash
source venv/bin/activate
\`\`\`

### Install Dependencies

\`\`\`bash
pip install -r requirements.txt
\`\`\`

### Deactivate Virtual Environment

\`\`\`bash
deactivate
\`\`\`

### Prepare OSRM Data

1. Create an `osrm-data` folder in the root directory
2. Download files from: [Google Drive Link](https://drive.google.com/drive/folders/12CYcHEcS29hpg7vrQt3C6OYICqJ08ydm?usp=sharing)
3. Extract all files from the drive and place them in the `osrm-data` folder

## Running the Server Infrastructure

### Start All Required Servers

1. Start Docker Desktop
2. Navigate to the project root directory
3. Run the Docker Compose configuration:

\`\`\`bash
docker compose up
\`\`\`

4. Monitor container status and logs through Docker Desktop application

## Backend Configuration

The system supports different study cases with varying numbers of bases (10, 20, and 60). Configuration changes are required based on the study case being tested.

### Configuration for 10 or 20 Base Study Cases

1. **Update Base Data:**
   - Retrieve base data for 20-base case from `/base_data/base_data.py`

2. **Modify Settings:**
   - Edit `./BackEnd/config/settings.py`
   - Update `BASE_DATA_INIT` variable with the 20-base data from step 1
   - Change `API_ORDER_RATE_SIMULATION_URL` to:
     \`\`\`
     http://order-rate-backend-simulation:5002
     \`\`\`

3. **Update Matrix API Client:**
   - Edit `./BackEnd/assets/matrix_api_client.py`
   - Change `api_order_rate_simulation_url` to:
     \`\`\`
     http://order-rate-backend-simulation:5002
     \`\`\`

### Configuration for 60 Base Study Case

1. **Update Base Data:**
   - Retrieve base data for 60-base case from `/base_data/base_data.py`

2. **Modify Settings:**
   - Edit `./BackEnd/config/settings.py`
   - Update `BASE_DATA_INIT` variable with the 60-base data from step 1
   - Change `API_ORDER_RATE_SIMULATION_URL` to:
     \`\`\`
     http://order-rate-backend-simulation-60-bases:5022
     \`\`\`

3. **Update Matrix API Client:**
   - Edit `./BackEnd/assets/matrix_api_client.py`
   - Change `api_order_rate_simulation_url` to:
     \`\`\`
     http://order-rate-backend-simulation-60-bases:5022
     \`\`\`

## Running the Web Frontend (Field Operator Dashboard)

1. Navigate to the `/FrontEnd` directory
2. Install dependencies:
   \`\`\`bash
   npm install
   \`\`\`
3. Start the development server:
   \`\`\`bash
   npm run dev
   \`\`\`
4. Access the web application at the provided URL (typically `localhost:3000`)

## Running the Mobile Application (Taxi Driver App)

### Prerequisites
- Install Expo Go app on your mobile device
- Ensure desktop and mobile devices are on the same local network

### Setup Steps

1. Navigate to the `/mobileTugasAkhir` directory
2. Install dependencies:
   \`\`\`bash
   npm install
   \`\`\`
3. **Configure Network Connection:**
   - Check your desktop's IP address on the local network:
     \`\`\`bash
     ipconfig
     \`\`\`
   - Note the IPv4 address for "Wireless LAN adapter Wi-Fi"
   - Edit `/mobileTugasAkhir/app.tsx`
   - Update the `BACKEND_URL` constant to:
     \`\`\`
     {your_desktop_ip}:5010
     \`\`\`

## QR Code Generation

Generate QR codes for base check-in functionality:

1. Navigate to the `/QR_Generator` directory
2. Install dependencies:
   \`\`\`bash
   npm install
   \`\`\`
3. Generate QR code for a specific base:
   \`\`\`bash
   node index.js {base_id}
   \`\`\`
   
   **Example:**
   \`\`\`bash
   node index.js 29355352
   \`\`\`

4. The QR code will be saved as a `.png` file in the `qr-codes` folder

### Pre-generated QR Codes

The repository includes sample QR codes for the 20-base study case:
- **Base 29355352** - Bandung Station
- **Base 5395151866** - Trans Studio Mall  
- **Base 11111111** - Unregistered base (for testing)

## Functional Requirements Testing

### Prerequisites
- Configure backend for 20-base study case (as described in Backend Configuration section)
- Run web frontend and mobile application as described above

### Setup Steps

1. **Register Field Operator:**
   - Sign up for field operator dashboard on the web application

2. **Register Taxi Driver:**
   - Sign up on mobile application as "taxi 0" (all functional test scripts use taxi 0 as reference)

3. **Generate Required QR Codes:**
   - Create QR codes for Bandung Station (base ID: 29355352) and other bases as needed

4. **Run Test Scripts:**
   - Activate the Python virtual environment created during initial setup
   - Navigate to `/simulation/functional test`
   - Execute test scripts based on the functional requirements table

### Functional Requirements Test Cases

| Test ID | Test Case | Procedure | Expected Result |
|---------|-----------|-----------|-----------------|
| FRT-01 | Successfully display fleet information | 1. Open dashboard as field operator 2. Click "Taxis" tab | Fleet data visible on map and table |
| FRT-02 | Successfully display base information | 1. Open dashboard as field operator 2. Click "Bases" tab | Base data is displayed |
| FRT-02 | Display base information changes when taxi checks in | 1. Simulate taxi in base area 2. Driver performs check-in 3. Open dashboard as field operator 4. Click "Bases" tab | Base state changes are reflected |
| FRT-02 | Validate taxi check-in based on location | 1. Simulate taxi outside base area 2. Taxi attempts check-in | Check-in fails due to location |
| FRT-02 | Validate taxi check-in based on slot availability | 1. Simulate base with full capacity 2. Taxi attempts check-in | Check-in fails due to full capacity |
| FRT-03 | Successfully receive base assignment | 1. Simulate taxi in specific area 2. Access driver account | Receive base assignment |
| FRT-04 | Successfully log base activity for taxi entry | 1. Simulate taxi in base area 2. Driver performs check-in 3. Open dashboard as field operator 4. Click "Base Activity Log" tab | Taxi entry is logged |

### Test Script Descriptions

**Available Test Scripts:**

- **FRT-02 (Schema-02):** Simulates taxi 0 entering Bandung Station base area to test check-in functionality
- **FRT-02 (Schema-03):** Tests check-in validation when taxi is outside the target base area  
- **FRT-02 (Schema-04):** Tests check-in when base capacity is full
- **FRT-03 (Schema-01):** Tests assignment notification system when taxi is in pool area
- **FRT-04 (Schema-01):** Tests activity logging when taxi checks into base
- **FRT-05 (Schema-01):** Tests timeout violation logging and notification system
- **FRT-05 (Schema-02):** Tests route deviation violation detection and logging
- **FRT-Integration:** Tests assignment cancellation when another taxi enters the assigned base first

### Important Testing Notes

**Server Reset Required:** Each functional test requires a fresh server state. Reset the server between tests:

\`\`\`bash
# Stop current containers
Ctrl+C
\`\`\`

\`\`\`bash
# Remove containers and volumes  
docker compose down -v
\`\`\`

\`\`\`bash
# Restart servers
docker compose up
\`\`\`

## Non-Functional Requirements Testing

### Setup

1. Configure backend for the appropriate base count study case (10, 20, or 60 bases)
2. Open a new terminal in the root directory
3. Activate the virtual environment:
   \`\`\`bash
   source venv/bin/activate
   \`\`\`
4. Navigate to `/simulation/skema/mqtt`
5. Run the Python script for the desired study case
6. Results will be generated as graphs in a new folder named after the study case

### Server Reset for Non-Functional Tests

**Server Reset Required:** Each non-functional test requires a fresh server state:

\`\`\`bash
# Stop current containers
Ctrl+C
\`\`\`

\`\`\`bash
# Remove containers and volumes
docker compose down -v
\`\`\`

\`\`\`bash
# Restart servers
docker compose up
\`\`\`

## Comparison Testing (Direct Assignment Without Base Assignment System)

For testing direct manual assignment scenarios without the base assignment system:

1. Open a new terminal in the root directory
2. Activate the virtual environment:
   \`\`\`bash
   source venv/bin/activate
   \`\`\`
3. Navigate to `/simulation/skema/non-mqtt`
4. Run the Python script for the desired study case
5. Results will be generated as graphs in a new folder named after the study case

## System Architecture Details

### Client-Side Components

**Mobile Application:**
- Built for taxi drivers
- Provides assignment notifications
- Handles base check-in functionality via QR code scanning
- Real-time location tracking and route guidance

**Web Application:**  
- Dashboard for field operators
- Fleet monitoring and management
- Base status monitoring
- Activity logging and violation tracking

### Server-Side Components

**Core Backend Services:**
- Assignment algorithm implementation
- Real-time communication via MQTT
- Database management for fleet and base data
- Integration with routing services (OSRM)

**Supporting Services:**
- Order rate simulation for different scenarios
- Distance/duration matrix calculations
- Database administration tools
- Message broker for real-time updates

## Development and Testing Workflow

1. **Initial Setup:** Clone repository, set up environment, prepare data
2. **Configuration:** Adjust backend settings based on study case requirements  
3. **Service Startup:** Launch all Docker containers
4. **Application Launch:** Start web and mobile applications
5. **Testing Execution:** Run functional or non-functional test suites
6. **Result Analysis:** Review generated logs and performance graphs

This comprehensive system enables thorough testing of EV taxi assignment algorithms under various scenarios and load conditions, providing insights into system performance and reliability.
