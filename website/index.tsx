import React from 'react';
import ReactDOM from 'react-dom/client';
import { FirebaseProvider } from './src/auth';
import { initializeAnalytics } from './src/utils/analytics';
import App from './App';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error("Could not find root element to mount to");
}

initializeAnalytics();

const root = ReactDOM.createRoot(rootElement);
root.render(
  <React.StrictMode>
    <FirebaseProvider>
      <App />
    </FirebaseProvider>
  </React.StrictMode>
);
