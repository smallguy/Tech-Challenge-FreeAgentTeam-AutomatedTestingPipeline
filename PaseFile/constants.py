"""常量和配置定义"""
from typing import List

DEFAULT_IMPORT_WHITELIST = [
    # Standard library
    'os', 'sys', 'json', 'csv', 'datetime', 'time', 'math', 'random', 're', 
    'urllib', 'pathlib', 'collections', 'itertools', 'functools', 'operator',
    'typing', 'copy', 'pickle', 'hashlib', 'base64', 'uuid', 'tempfile',
    'shutil', 'glob', 'fnmatch', 'zipfile', 'tarfile', 'gzip', 'bz2',
    'io', 'sqlite3', 'configparser', 'argparse', 'logging', 'warnings',
    
    # Data science core libraries
    'numpy', 'np', 'pandas', 'pd', 'matplotlib', 'plt', 'seaborn', 'sns',
    'scipy', 'sklearn', 'plotly', 'dash', 'streamlit',
    
    # Machine learning frameworks
    'torch', 'torchvision', 'torchaudio', 'transformers', 'tensorflow', 'tf',
    'keras', 'jax', 'flax', 'optax',
    
    # Image processing
    'PIL', 'Image', 'cv2', 'skimage', 'imageio',
    
    # Network and data acquisition
    'requests', 'urllib3', 'beautifulsoup4', 'bs4', 'scrapy', 'selenium',
    
    # File processing
    'openpyxl', 'xlrd', 'xlwt', 'xlsxwriter', 'h5py', 'netCDF4', 'pyarrow',
    
    # Other common tools
    'tqdm', 'joblib', 'multiprocessing', 'concurrent', 'threading',
    'psutil', 'memory_profiler', 'line_profiler',
]

# Code file extensions for truncation
CODE_EXTENSIONS = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.cs', 
                  '.php', '.rb', '.go', '.rs', '.swift', '.jsx', '.tsx', 
                  '.vue', '.svelte', '.kt', '.scala', '.clj', '.hs', '.ml', 
                  '.sh', '.bash', '.ps1', '.sql', '.r', '.m', '.ipynb'}

# Sandbox types
SANDBOX_TYPES = ["internal_python", "jupyter", "docker", "subprocess", "e2b"]