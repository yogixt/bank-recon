import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '';

const client = axios.create({
  baseURL: `${API_URL}/api`,
  headers: { 'Content-Type': 'application/json' },
});

// Intercept requests to debug the outgoing payload
client.interceptors.request.use((config) => {
  console.log('[Axios Request]', config.method?.toUpperCase(), config.url);
  if (config.data instanceof FormData) {
    console.log('[Axios FormData Keys]', Array.from(config.data.keys()));
  }
  return config;
});

// Intercept responses to debug errors
client.interceptors.response.use(
  (response) => {
    console.log('[Axios Response]', response.status, response.data);
    return response;
  },
  (error) => {
    console.error('[Axios Error]', error.message);
    if (error.response) {
      console.error('[Axios Error Response]', error.response.status, error.response.data);
    }
    return Promise.reject(error);
  }
);

export default client;
