import numpy as np # type: ignore
import pandas as pd # type: ignore
import io
import os
from typing import Optional, Any, List
from sklearn.impute import KNNImputer # type: ignore
from sklearn.preprocessing import MinMaxScaler, StandardScaler, RobustScaler, MaxAbsScaler # type: ignore

def read_data(file_input, filter: Optional[str] = None) -> pd.DataFrame:
    '''
    Reads a csv file with optional filtering by identifier
    '''
    try:
        # Check if input is a BytesIO object
        if isinstance(file_input, io.BytesIO):
            # Reset position to beginning of stream
            file_input.seek(0)
            df = pd.read_csv(file_input)
        
        # Check if input is a file path string
        elif isinstance(file_input, str):
            if not os.path.exists(file_input):
                raise FileNotFoundError(f"File not found: {file_input}")
            df = pd.read_csv(file_input)
        
        # Handle other file-like objects
        else:
            df = pd.read_csv(file_input)
        
    except pd.errors.EmptyDataError:
        raise ValueError("CSV file is empty")
    except pd.errors.ParserError as e:
        raise ValueError(f"Error parsing CSV: {e}")
    except UnicodeDecodeError:
        # Try different encodings
        try:
            if isinstance(file_input, io.BytesIO):
                file_input.seek(0)
                df = pd.read_csv(file_input, encoding='latin-1')
            else:
                df = pd.read_csv(file_input, encoding='latin-1')
            return df
        except:
            if isinstance(file_input, io.BytesIO):
                file_input.seek(0)
                df = pd.read_csv(file_input, encoding='cp1252')
            else:
                df = pd.read_csv(file_input, encoding='cp1252')
            return df
    except Exception as e:
        raise ValueError(f"Error reading CSV data: {e}")

    try:
        df['time'] = pd.to_datetime(df['time'])
    except:
        raise ValueError('No column labeled \'time\'')

    # Selects only data for user-defined identifer
    if filter is not None:
        df = df.loc[df['District'] == filter]
        df.drop(['District'], axis=1, inplace=True)
        if isinstance(df, pd.Series):
            df = df.to_frame().T  # Ensure return type is always DataFrame
    
    # Index is set to the time so it doesn't clog other functions that can only operate on numerical data types
    try:
        df.set_index(pd.DatetimeIndex(df['time']), inplace=True)
        df.drop(['time'], axis=1, inplace=True)
    except:
        raise Exception("Error: Could not set 'time' column as index")

    # Casts all numeric values to float64 for minimal data loss in the case of high precision values
    numeric_cols = df.select_dtypes(include=np.number).columns
    df[numeric_cols] = df[numeric_cols].astype(np.float64)

    return df

def select_numeric(df: pd.DataFrame) -> pd.DataFrame:
    return df.copy().select_dtypes(include=np.number)

def handle_nans(df: pd.DataFrame, threshold: float = 0.33, window: int = 2, no_drop: bool = True) -> pd.DataFrame:
    """
    Handle NaN values in the DaSaFrame by dropping rows with too many NaNs.
    Threshold is the highest percentage of NaNs allowed in a row.
    Rows with more than this percentage of NaNs will be dropped.
    Remaining NaNs will be filled by KNN imputation.
    Window is the number of nearby non-NaN values used in imputation.
    """
    df_return = select_numeric(df)
    features = df_return.columns

    # Drop rows with too many NaNs
    if not no_drop:
        thresh_not_missing = np.ceil(len(features) * (1 - threshold))
        df_return.dropna(axis=0, thresh=thresh_not_missing, inplace=True)

    # Drop columns with only NaNs
    df_return.dropna(axis=1, how='all', inplace=True)

    # Impute missing values via KNNImputer (sci-kit learn)
    for col in features:
        imputer = KNNImputer(n_neighbors=window, weights='distance', copy=True)
        array_col = df_return[col].to_numpy().reshape(-1, 1)
        preserve_index = df_return[col].index
        df_return[col] = pd.Series(imputer.fit_transform(array_col).flatten(), index=preserve_index)

    return df_return

def scale_data(df: pd.DataFrame, scale: Any="StandardScaler") -> tuple[pd.DataFrame, Any]:
    df_return = select_numeric(df)
    
    if scale is None:
        return df_return, None

    if isinstance(scale, str):
        match scale:
            case 'StandardScaler':
                scaler = StandardScaler()
            case 'MinMaxScaler':
                scaler = MinMaxScaler()
            case 'RobustScaler':
                scaler = RobustScaler()
            case 'MaxAbsScaler':
                scaler = MaxAbsScaler()
            case _:
                raise ValueError('Argument passed is not a supported scaler')
    else:
        if not isinstance(scale, (StandardScaler, MinMaxScaler, RobustScaler, MaxAbsScaler)):
            raise TypeError('Argument passed is not a supported scaler')
        scaler = scale
        
    df_return = pd.DataFrame(scaler.fit_transform(df_return), index=df.index, columns=df.columns)

    return df_return, scaler

def clip_outliers(df: pd.DataFrame, cols: Optional[List] = None, method: str = "iqr", factor: float = 1.5) -> pd.DataFrame:
    """
    Clip outliers in specified columns of a dataframe.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe.
    cols : list, optional
        List of columns to clip. If None, all numeric columns are clipped.
    method : str, default "iqr"
        Method to detect outliers: "iqr" or "percentile".
    factor : float, default 1.5
        Factor for IQR method, or percentile range (e.g., 0.01 → clip 1st/99th percentile).

    Returns
    -------
    pd.DataFrame
        DataFrame with clipped values.
    """
    df_clipped = select_numeric(df)
    if cols is None:
        cols = df_clipped.columns.tolist()
    
    for col in cols:
        if method == "iqr":
            Q1 = df_clipped[col].quantile(0.25)
            Q3 = df_clipped[col].quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - factor * IQR
            upper = Q3 + factor * IQR
        elif method == "percentile":
            lower = df_clipped[col].quantile(factor)
            upper = df_clipped[col].quantile(1 - factor)
        else:
            raise ValueError("method must be 'iqr' or 'percentile'")
        
        df_clipped[col] = df_clipped[col].clip(lower=lower, upper=upper)
    
    return df_clipped

def generate_lags(df: pd.DataFrame, n_lags: int, step: int=1) -> pd.DataFrame:
    '''
    Generates duplicate n_lags duplicate features that are lagged by step
    '''
    df_n = df.copy()
    columns = df.columns
    sampling = check_uniform(df)
    dfs = []

    for n in range(step, step*n_lags + 1, step):
        for col in columns:
            df_n[f"{col}_lag(-{n})"] = df_n[col].shift(n, freq=sampling)
    df_n = df_n.iloc[n_lags:]

    dfs.append(df_n)
    df_return = pd.concat(dfs, ignore_index=False)

    return df_return

def check_uniform(df: pd.DataFrame) -> pd.Timedelta:
    '''
    Assuming a dataframe with a datetime index, this function checks for uniformity
    in sampling and returns the most common Timedelta
    '''

    # Ensure the index is a DatetimeIndex for reliable Timedelta operations
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("DataFrame index must be a DatetimeIndex.")
    
    time_diffs: pd.Series = df.index.to_series().diff()
    time_diffs_mode = time_diffs.mode()

    if not time_diffs_mode.empty:
        # Explicitly extract the first element and cast it to pd.Timedelta.
        most_common_frequency = pd.Timedelta(time_diffs_mode.iloc[0])
    else:
        # If there's less than 2 data points, diff() will be all NaT or empty,
        # leading to an empty mode.
        raise ValueError('Cannot determine most common frequency, not enough valid time differences.')

    tolerance = pd.Timedelta(milliseconds=10)
    time_diffs[abs(time_diffs - most_common_frequency) <= tolerance] = most_common_frequency

    diff_counts = time_diffs.value_counts().sort_index()

    if diff_counts.empty:
        raise ValueError('No valid time differences found to calculate frequency.')

    total_observations = len(time_diffs)
    count_most_common = diff_counts.loc[most_common_frequency]
    percentage_most_common = (count_most_common / total_observations) * 100
        
    if percentage_most_common < 75:
        print(f"Most common frequency accounts for {percentage_most_common:.2f}% of the time steps.")
        print('Warning: sampling frequency is highly irregular. Resampling is strongly recommended')
    elif percentage_most_common < 98:
        print(f"Most common frequency accounts for {percentage_most_common:.2f}% of the time steps.")
        print('Warning: sampling frequency is irregular. Resampling is recommended')

    return most_common_frequency

def time_to_feature(df: pd.DataFrame):
    '''
    Creates features for cyclical representations of time to help ML models identify seasonality.
    Cyclic representations are necessary to show that 23:59 is very close to 0:00
    '''
    df_return = df.copy()

    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("DataFrame index must be a DatetimeIndex.")
    

    df_return = (
        df_return
        .assign(min_of_day=(df.index.hour*60 + df.index.minute))
        .assign(day_of_week=df.index.dayofweek)
        .assign(day_of_year=df.index.dayofyear)
    )

    time_features = {'min_of_day': 1440, 'day_of_week': 7, 'day_of_year': 365.25}

    for feature, period in time_features.items():
        df_return[f"{feature}_sin"] = np.sin((df_return[feature]) * (2 * np.pi / period))
        df_return[f"{feature}_cos"] = np.cos((df_return[feature]) * (2 * np.pi / period))
        df_return = df_return.drop(columns=[feature])

    return df_return

def window_data(df: pd.DataFrame | np.ndarray,
                exo_features: Optional[List[str]] = None,
                input_len: int = 10,
                output_len: int = 1) -> tuple[np.ndarray, np.ndarray, Optional[Any]]:
    """Create sliding windows.

    Supports two invocation styles:
    1. DataFrame invocation (preferred): pass a DataFrame containing a 'value' target column plus any
       exogenous feature columns. Provide ``exo_features`` list if you want target to exclude them.
       Returns (X, y, None) where X shape == (num_windows, input_len, n_features) and
       y shape == (num_windows, output_len, n_target_features).
    2. Legacy ndarray invocation (values, features): if ``df`` is an ndarray we assume the caller already
       prepared 1-D target array and 2-D feature matrix and concatenated them externally. This path is kept
       only for backward compatibility. In that case provide df as a 2D array and set ``exo_features`` to None.
    """

    scaler_obj = None

    # Case 2: raw ndarray (fallback) – treat entire array as features with first column the target
    if isinstance(df, np.ndarray):
        if df.ndim == 1:
            # Only target series provided; build simple window dataset
            series = df.astype(np.float32)
            n_rows = series.shape[0]
            n_features = 1
            n_windows = n_rows - input_len - output_len + 1
            if n_windows <= 0:
                raise ValueError("Not enough rows to create a single window")
            X = np.zeros((n_windows, input_len, n_features), dtype=np.float32)
            Y = np.zeros((n_windows, output_len, n_features), dtype=np.float32)
            for i in range(n_windows):
                X[i, :, 0] = series[i:i+input_len]
                Y[i, :, 0] = series[i+input_len:i+input_len+output_len]
            return X, Y, scaler_obj
        else:
            raise ValueError("For ndarray input expected 1D target series; got shape %s" % (df.shape,))

    # Case 1: DataFrame path
    if not isinstance(df, pd.DataFrame):
        raise TypeError("window_data expects a pandas DataFrame or 1D numpy array")

    if 'value' not in df.columns:
        raise ValueError("DataFrame must contain a 'value' column for target")

    # Determine endogenous (target) vs exogenous features
    if exo_features is not None:
        x_df = df.copy()
        y_df = df.drop(columns=exo_features)
    else:
        x_df = df.copy()
        y_df = df[['value']]  # ensure y only contains target

    n_rows = x_df.shape[0]
    n_feat = x_df.shape[1]
    n_target = y_df.shape[1]

    n_windows = n_rows - input_len - output_len + 1
    if n_windows <= 0:
        raise ValueError("Not enough rows (%d) for input_len=%d output_len=%d" % (n_rows, input_len, output_len))

    X = np.zeros((n_windows, input_len, n_feat), dtype=np.float32)
    Y = np.zeros((n_windows, output_len, n_target), dtype=np.float32)

    for start in range(n_windows):
        end_in = start + input_len
        end_out = end_in + output_len
        X[start, :, :] = x_df.iloc[start:end_in, :].to_numpy(dtype=np.float32)
        Y[start, :, :] = y_df.iloc[end_in:end_out, :].to_numpy(dtype=np.float32)

    return X, Y, scaler_obj

def subset_scaler(original_scaler, original_columns, subset_columns):
    """
    Creates a new scaler for a subset of features from an existing fitted scaler.
    Supports StandardScaler, MinMaxScaler, RobustScaler, MaxAbsScaler, and LogScaler.

    Args:
        original_scaler: The fitted scaler object.
        original_columns (list): The column names from the original DataFrame.
        subset_columns (list): A list of column names for the new scaler.

    Returns:
        A new, configured scaler for the subset of data.
    """
    if original_columns == subset_columns:
        return original_scaler

    # Find the integer indices of the subset columns
    subset_indices = [original_columns.index(col) for col in subset_columns]

    if isinstance(original_scaler, StandardScaler):
        subset = StandardScaler()
        if original_scaler.mean_ is not None:
            subset.mean_ = original_scaler.mean_[subset_indices]
        else:
            subset.mean_ = None
        if original_scaler.scale_ is not None:
            subset.scale_ = original_scaler.scale_[subset_indices]
        else:
            subset.scale_ = None

    elif isinstance(original_scaler, MinMaxScaler):
        subset = MinMaxScaler()
        subset.min_ = original_scaler.min_[subset_indices]
        subset.scale_ = original_scaler.scale_[subset_indices]
        subset.data_min_ = original_scaler.data_min_[subset_indices]
        subset.data_max_ = original_scaler.data_max_[subset_indices]
        subset.data_range_ = original_scaler.data_range_[subset_indices]

    elif isinstance(original_scaler, RobustScaler):
        subset = RobustScaler()
        subset.center_ = original_scaler.center_[subset_indices]
        subset.scale_ = original_scaler.scale_[subset_indices]

    elif isinstance(original_scaler, MaxAbsScaler):
        subset = MaxAbsScaler()
        subset.max_abs_ = original_scaler.max_abs_[subset_indices]
        subset.scale_ = original_scaler.scale_[subset_indices]

    else:
        raise TypeError("Unsupported scaler type. This function only supports "
                        "StandardScaler, MinMaxScaler, RobustScaler, MaxAbsScaler, and LogScaler.")

    # Set feature info for scikit-learn validation
    subset.n_features_in_ = len(subset_columns)
    subset.feature_names_in_ = np.array(subset_columns, dtype=object)

    return subset
