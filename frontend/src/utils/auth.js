export const getAuthToken = () => {
  const token = localStorage.getItem('token');
  if (!token) {
    console.error('No auth token found in localStorage');
    return null;
  }
  return token;
};

export const setAuthToken = (token) => {
  localStorage.setItem('token', token);
};

export const removeAuthToken = () => {
  localStorage.removeItem('token');
};

export const isAuthenticated = () => {
  return !!getAuthToken();
};
