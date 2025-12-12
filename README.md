<div style="text-align: center">
  <img src="app/static/img/logos/logo-weather-dark.png" alt="Weather-hub Logo" />
</div>

# 🌦️ Weather-Hub

**Weather-Hub** is a centralized repository of *meteorological datasets* designed to facilitate data analysis, academic research, and machine learning model development. The goal is to provide clean, well-organized, and thoroughly documented data related to weather phenomena following Open Science principles.

---

## 🌍 Project Deployment on Render

Weather-Hub is currently deployed in two separate instances:

### ☁️ Production Environment
**URL:** https://weather-hub-1.onrender.com

This is the stable, production-ready instance with the latest released version.

### 🌧️ Development Environment
**URL:** https://weather-hub-1-trunk.onrender.com

This instance is updated with the latest development changes from the main branch and is used for testing new features before production release.

---
## 🚀 Local Installation

Weather-Hub includes a simple configuration to create a complete and reproducible development environment.

### 📋 Prerequisites

- **Python**: 3.12 or higher
- **pip**: Python package manager
- **Git**: Version control
- **Terminal/Console Access**: For executing commands

### 🔧 Manual Step-by-Step Installation

Follow these steps to set up your development environment:

#### 1. Clone the repository
```bash
git clone https://github.com/weather-hub/weather-hub-1.git
cd weather-hub-1
```

#### 2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate
```

#### 3. Install dependencies
```bash
pip install -r requirements.txt
pip install -e ./
```

#### 4. Apply Migrations
```bash
flask db upgrade
```

#### 5. Populate Database
```bash
rosemary db:seed
```

#### 6. Configure pre-commit hooks
```bash
pre-commit install
pre-commit install --hook-type commit-msg
```

#### 7. Run the application
```bash
flask run --host=0.0.0.0 --reload --debug
```

If everything worked correctly, you should see Weather-Hub deployed in development at: `http://localhost:5000`

### 🛠️ Environment Configuration

The project is automatically configured with:

- **Python 3.12+** as the base interpreter
- **MariaDB** as the relational database
- **Isolated virtual environment** in the `venv/` folder
- **Project dependencies** installed from `requirements.txt`
- **Rosemary** CLI tool installed in editable mode for development
- **Pre-commit hooks** to ensure code quality
- **Commit-msg hooks** to maintain consistency in commit messages
- **Flask development server** with auto-reload and debug mode

### ⚙️ Customization

If you need to modify the configuration:

- **Database credentials**: Edit `.env` file in the project root
- **Dependencies**: Edit `requirements.txt` and run `pip install -r requirements.txt`
- **Environment variables**: Add or modify variables in `.env`
- **Application configuration**: Modify `app.py` or configuration files as needed

---

## 🤝 Contributing

If you want to contribute to the Weather-Hub project, please:

1. **Fork** the repository
2. **Create a branch** for your feature (`git checkout -b feature/YourFeature`)
3. **Commit your changes using conventional commits**(`git commit -m 'feat: Add a new feature'`
   `'fix: Bug fix'`
   `'docs: Documentation only changes'`)
4. **Push to the branch** (`git push origin feature/YourFeature`)

Please ensure that your changes:
- Pass the pre-commit hooks
- Include descriptive commit messages
- Follow the existing code structure

## 📧 Contact and Support

- 🐛 Open an issue on the repository to [report a bug](https://github.com/weather-hub/weather-hub-1/issues/new?template=bug_report.md)
- 💡 [Request a feature](https://github.com/weather-hub/weather-hub-1/issues/new?template=feature_request.md)
- 📖 [Check the Wiki](https://github.com/weather-hub/weather-hub-1/wiki)
- 📚 [Official Documentation](https://docs.uvlhub.io/)

---

**Developed by Weather-Hub-1** 🌍🌦️
