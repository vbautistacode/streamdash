import pandas as pd
from etl.transformers import validate_dataframe

def test_validate_dataframe():
    df = pd.DataFrame({"mes": ["2025-01-01", None], "receita": [100, 200]})
    df_valid = validate_dataframe(df)
    assert df_valid["mes"].notnull().all()
