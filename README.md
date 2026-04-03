# Margadarshak

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node.js-18+-green.svg)](https://nodejs.org/)

An AI-driven smart traffic control system that leverages Graph Neural Networks (GNN) and Reinforcement Learning (RL) to optimize traffic signal timings and reduce congestion in urban environments. Built with FastAPI backend, React frontend, and integrated with SUMO for traffic simulation.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [API Documentation](#api-documentation)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Real-time Traffic Simulation**: Integrates with SUMO (Simulation of Urban Mobility) for accurate traffic modeling.
- **AI-Powered Optimization**: Uses GNN for spatial traffic analysis and RL for adaptive signal control.
- **Interactive Dashboard**: Web-based interface for monitoring traffic metrics, visualizing maps, and controlling simulations.
- **Modular Architecture**: Separated backend (Python/FastAPI), frontend (React), and simulation components.
- **WebSocket Support**: Real-time updates via WebSockets for live simulation data.
- **Extensible Models**: Pre-trained GNN and RL models with training capabilities.

## Requirements

- Python 3.10 or higher
- Node.js 18 or higher
- SUMO 1.20 or higher
- Git

## Installation

### Clone the Repository

```bash
git clone https://github.com/yourusername/margadarshak.git
cd margadarshak
```

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

3. Activate the virtual environment:
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Copy the environment file (if available):
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your configuration.

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd ../frontend
   ```

2. Install Node.js dependencies:
   ```bash
   npm install
   ```

### SUMO Installation

Download and install SUMO from the [official website](https://www.eclipse.org/sumo/). Ensure `sumo` and `sumo-gui` are in your PATH.

## Usage

### Running the Backend

From the `backend` directory with the virtual environment activated:

```bash
uvicorn app:app --reload
```

The API will be available at `http://localhost:8000`.

### Running the Frontend

From the `frontend` directory:

```bash
npm run dev
```

The dashboard will be available at `http://localhost:5173` (default Vite port).

### Running a Simulation

1. Ensure SUMO network files are in `data/sumo_networks/`.
2. Use the API endpoints or scripts in `scripts/` to generate routes and start simulations.
3. Monitor via the frontend dashboard.

For detailed API usage, see [API Documentation](#api-documentation).

## Project Structure

```
margadarshak/
├── backend/                 # FastAPI backend
│   ├── app.py              # Main application entry point
│   ├── requirements.txt    # Python dependencies
│   └── src/
│       ├── api/            # API endpoints
│       ├── brain/          # AI models (GNN, RL)
│       ├── osm_pipeline/   # OSM data processing
│       ├── sensing/        # Traffic sensing and features
│       ├── simulation/     # SUMO integration
│       └── utils/          # Utility functions
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Dashboard pages
│   │   └── services/       # API services
│   └── package.json        # Node dependencies
├── data/                   # Data files
│   ├── configs/            # SUMO configuration files
│   ├── osm_raw/            # Raw OSM data
│   ├── routes/             # Generated routes
│   └── sumo_networks/      # SUMO network files (ignored by git)
├── scripts/                # Utility scripts
├── tests/                  # Test files
├── LICENSE                 # Open-source license
└── README.md               # This file
```

### Notes
- `backend/cache/` stores runtime simulation caching and is gitignored by default.
- `backend/models/` includes local ML checkpoints and prepared policies; these are large binary files and should not be committed unless explicitly needed.
- `frontend/node_modules/` and `frontend/dist/` are generated and gitignored.
- For reproducible environments, commit only source files and lockfiles (`requirements.txt`, `package.json`).

## API Documentation

Once the backend is running, visit `http://localhost:8000/docs` for interactive API documentation powered by Swagger UI.

Key endpoints:
- `/api/simulation/` - Simulation control
- `/api/map/` - Map data
- `/api/metrics/` - Traffic metrics

## Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin feature/your-feature-name`
5. Submit a pull request.

Please ensure all tests pass and add tests for new features.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/) and [React](https://reactjs.org/)
- Traffic simulation powered by [SUMO](https://www.eclipse.org/sumo/)
- AI models using [PyTorch](https://pytorch.org/) and [PyTorch Geometric](https://pytorch-geometric.readthedocs.io/)
