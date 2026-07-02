import pandas as pd
from pathlib import Path

dir = Path('raw/')
for file in dir.iterdir():
    if file.is_file():
        df = pd.read_csv(file)
        df = df.set_index('Date')
        df.index = pd.to_datetime(df.index)
        
        # Drop NaNs and duplicates
        df.dropna(inplace=True)
        df.drop_duplicates(inplace=True)
        
        df.to_csv(f"processed/{file.name}")
        print(f"Saved {file.name}")