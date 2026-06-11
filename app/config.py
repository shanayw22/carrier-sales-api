import os

from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
API_KEY = os.environ["API_KEY"]
FMCSA_API_KEY = os.environ["FMCSA_API_KEY"]
FMCSA_BASE_URL = "https://mobile.fmcsa.dot.gov/qc/services/carriers"