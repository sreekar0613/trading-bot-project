import numpy as np
import pandas as pd
import joblib
from hmmlearn import hmm
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

class MarketRegimeDetector:
    def __init__(self, model_path=REPO_ROOT / "regime_model.pkl"):
        self.model = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=1000, random_state=42)
        self.model_path = model_path
        self.is_fitted = False
    
    def _prepare_features(self, spy_df):
        # Calculate daily log returns
        log_ret = np.log(spy_df['Close'] / spy_df['Close'].shift(1))
        # Calculate realized volatility (e.g. 10-day rolling std of log returns)
        volatility = log_ret.rolling(window=10).std()
        
        df_clean = pd.DataFrame({'log_ret': log_ret, 'volatility': volatility}).dropna()
        features = np.column_stack([df_clean['log_ret'], df_clean['volatility']])
        return features, df_clean
        
    def fit(self, spy_df):
        features, _ = self._prepare_features(spy_df)
        self.model.fit(features)
        
        # Persistently label the states based on volatility
        # We expect:
        # State 0: Low-Vol Bull (lowest vol)
        # State 1: High-Vol Bear (highest vol)
        # State 2: Sideways (medium vol)
        
        means = self.model.means_
        # means[:, 1] is the mean of the 'volatility' feature for each state
        vol_means = means[:, 1]
        sorted_indices = np.argsort(vol_means)
        
        mapping = {}
        mapping[sorted_indices[0]] = 0  # Lowest vol -> State 0
        mapping[sorted_indices[1]] = 2  # Medium vol -> State 2
        mapping[sorted_indices[2]] = 1  # Highest vol -> State 1
        
        # Reorder the model parameters
        perm = np.zeros(3, dtype=int)
        for old_idx, new_idx in mapping.items():
            perm[new_idx] = old_idx
            
        new_model = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=self.model.n_iter, random_state=self.model.random_state)
        new_model.startprob_ = self.model.startprob_[perm]
        new_model.transmat_ = self.model.transmat_[np.ix_(perm, perm)]
        new_model.means_ = self.model.means_[perm]
        new_model.covars_ = self.model.covars_[perm]
        
        self.model = new_model
        self.is_fitted = True

    def predict(self, spy_df):
        if not self.is_fitted:
            try:
                self.load()
            except Exception as e:
                # Fallback to fit on provided df if load fails
                self.fit(spy_df)
                
        features, _ = self._prepare_features(spy_df)
        states = self.model.predict(features)
        return int(states[-1])

    def predict_all(self, spy_df):
        """Helper to predict regimes for a whole dataframe (for backtesting)."""
        if not self.is_fitted:
            self.fit(spy_df)
        features, df_clean = self._prepare_features(spy_df)
        states = self.model.predict(features)
        
        # Return a series indexed by df_clean's index
        return pd.Series(states, index=df_clean.index)

    def save(self):
        joblib.dump(self.model, self.model_path)

    def load(self):
        self.model = joblib.load(self.model_path)
        self.is_fitted = True
