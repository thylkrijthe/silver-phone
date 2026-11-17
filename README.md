# Silver tracker for phones

The app has three sections. **My silver** values a weight in kilograms or troy ounces. **Price history** shows zoomable daily prices and a recent intraday view with an optional one-minute refresh. **Strategy lab** runs single-strategy, comparison and walk-forward backtests and exports the results. Prices use silver futures as a reference, converted into euros. The latest quote time is shown.

## Put it online and share privately

1. Extract the ZIP. Create a **private** GitHub repository and add the files inside the `silver-phone` folder to its root, including `.streamlit/config.toml` if using the supplied theme. The entry file is `app.py`.
2. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/) and connect GitHub. Under **Linked accounts → Source control**, authorize access to private repositories if needed.
3. Select **Create app → Yup, I have an app**. Choose the repository and branch, set the main file path to `app.py`, and choose Python **3.14** under **Advanced settings**. Click **Deploy**.
4. Once it loads, open **Share**, verify only specific people can view it, and invite your father using his email. He can open the link in Safari or Chrome and sign in with Google or an emailed one-time link. He needs no GitHub account and your Mac can be off.

Keep your notebook’s `silver_holding.json` and results out of the repository. This app keeps the entered quantity in the visitor’s current session. A fresh session can require entering it again. The intraday view refreshes while it is open, and Yahoo Finance prices may be delayed. Neither the app nor the backtest places trades.

## Try it on your Mac first

From the project folder:

```bash
~/python-envs/mude/bin/python -m pip install -r requirements.txt
~/python-envs/mude/bin/python -m streamlit run app.py
```

Open the URL shown in your terminal. To test private sharing, use a different browser or a private window after deployment.

[Streamlit deployment instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) · [Private app sharing](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app)
