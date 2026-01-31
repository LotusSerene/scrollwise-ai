// Basic fetch wrapper for interacting with the backend API
const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

if (!API_BASE_URL) {
  console.warn(
    "Warning: NEXT_PUBLIC_BACKEND_URL is not defined. API calls may fail."
  );
  // Optionally throw an error in production builds
  // if (process.env.NODE_ENV === 'production') {
  //   throw new Error("NEXT_PUBLIC_BACKEND_URL is not defined in the environment.");
  // }
}

// Helper function for development-only logging
const devLog = (message: string, data?: unknown) => {
  if (process.env.NODE_ENV !== "production") {
    if (data) {
      console.log(message, data);
    } else {
      console.log(message);
    }
  }
};

/**
 * Fetches data from the backend API.
 * Handles base URL and basic error handling.
 * Assumes JSON responses.
 *
 * @param endpoint The API endpoint path (e.g., '/projects').
 * @param options Standard fetch options (method, headers, body, etc.).
 * @param authToken Optional JWT token for authenticated requests.
 * @returns The JSON response data.
 * @throws {Error} If the fetch fails or the response is not ok.
 */
export async function fetchApi<T = unknown>(
  endpoint: string,
  options: RequestInit = {},
  authToken?: string | null // Use explicitly passed token
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const requestHeaders: Record<string, string> = {
    Accept: "application/json",
    ...(options.headers as Record<string, string>),
  };

  // Do not set Content-Type for FormData, let the browser handle it
  if (!(options.body instanceof FormData)) {
    requestHeaders["Content-Type"] = "application/json";
  }

  // Add Authorization header ONLY if authToken is provided
  if (authToken) {
    requestHeaders["Authorization"] = `Bearer ${authToken}`;
    devLog("fetchApi: Authorization header set from provided token.");
  } else {
    devLog(
      `fetchApi: No auth token provided for request to ${endpoint}. Request may fail.`
    );
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers: requestHeaders, // Use the modified headers object
    });

    if (!response.ok) {
      let errorBody;
      try {
        errorBody = await response.json(); // Try to parse error details from backend
      } catch {
        // Removed unused error variable
        // Ignore if error body isn't JSON
      }
      console.error(
        `API Error: ${response.status} ${response.statusText}`,
        errorBody
      );
      throw new Error(
        `API request failed: ${response.status} ${response.statusText}. ${
          errorBody?.detail || (errorBody ? JSON.stringify(errorBody) : "")
        }`
      );
    }

    // Handle cases where the response might be empty (e.g., DELETE requests, 204 No Content)
    // Removed unreliable content-length check
    if (response.status === 204) {
      devLog("fetchApi: Returning null for 204 No Content status.");
      // Return null (or potentially an empty object/array depending on conventions)
      // Casting to T might be problematic if T expects a specific structure, but null is common for empty responses.
      // Consider how calling code handles null when expecting T.
      return null as T;
    }

    // For all other successful responses (like 200 OK), attempt to parse JSON
    try {
      devLog(
        `fetchApi: Attempting response.json() for status ${response.status}`
      );
      const jsonData = await response.json();
      // Only log in development, and never log the actual response data in production
      devLog("fetchApi: response.json() successful");
      return jsonData as T;
    } catch (jsonError) {
      console.error("fetchApi: response.json() FAILED!", jsonError);
      // Log the raw text to see what response.json() choked on
      try {
        const text = await response.text();
        console.error(
          "fetchApi: Raw response text that failed JSON parsing:",
          text.substring(0, 200) + (text.length > 200 ? "..." : "") // Only log beginning of response
        );
      } catch (textError) {
        console.error(
          "fetchApi: Could not get raw text from response after JSON failure.",
          textError
        );
      }
      // Decide how to handle JSON parsing failure. Rethrowing might be best.
      throw new Error(`Failed to parse JSON response: ${jsonError}`);
    }
  } catch (error) {
    console.error(`Fetch API error for ${url}:`, error);
    // Re-throw the error to be handled by the calling component/function
    throw error;
  }
}

/**
 * Fetches a file/blob from the backend API.
 * Handles base URL and authentication.
 *
 * @param endpoint The API endpoint path.
 * @param options Standard fetch options (method, headers, body, etc.).
 * @param authToken Optional JWT token.
 * @returns An object containing the Blob and the Response Headers.
 * @throws {Error} If the fetch fails or the response is not ok.
 */
export async function fetchFileApi(
  endpoint: string,
  options: RequestInit = {},
  authToken?: string | null // Use explicitly passed token
): Promise<{ blob: Blob; headers: Headers }> {
  const envBackendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;
  const url = `${envBackendUrl}${endpoint}`;

  const requestHeaders: Record<string, string> = {
    Accept: "*/*",
    ...(options.headers as Record<string, string>),
  };

  // Add Authorization header ONLY if authToken is provided
  if (authToken) {
    requestHeaders["Authorization"] = `Bearer ${authToken}`;
    devLog("fetchFileApi: Authorization header set from provided token.");
  } else {
    devLog(
      `fetchFileApi: No auth token provided for file request to ${endpoint}. Request may fail.`
    );
  }

  // Remove Content-Type if it was accidentally set for a GET request
  // Or ensure it's appropriate if options included a body (though unlikely for file download)
  if (options.method === "GET" || !options.body) {
    delete requestHeaders["Content-Type"];
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers: requestHeaders,
    });

    if (!response.ok) {
      let errorDetail = `File request failed: ${response.status} ${response.statusText}`;
      try {
        // Try to get more details if the error response is JSON
        const errorJson = await response.json();
        errorDetail = errorJson.detail || JSON.stringify(errorJson);
      } catch {
        /* Ignore if error body isn't JSON */
      }
      console.error(
        `API File Error: ${response.status} ${response.statusText}`,
        errorDetail
      );
      throw new Error(errorDetail);
    }

    // Get the blob data
    const blob = await response.blob();

    // Return blob and headers
    return { blob, headers: response.headers };
  } catch (error) {
    console.error(`Fetch File API error for ${url}:`, error);
    throw error; // Re-throw
  }
}

// Function to save the OpenRouter API key
export async function saveOpenRouterApiKey(
  apiKey: string,
  authToken: string
): Promise<{ message: string }> {
  return fetchApi(
    `/settings/openrouter-api-key`,
    {
      method: "POST",
      body: JSON.stringify({ openrouterApiKey: apiKey }),
    },
    authToken
  );
}

// Function to check the OpenRouter API key status
// Assuming the response format is the same as the Gemini key check
export async function checkOpenRouterApiKey(
  authToken: string
): Promise<{ isSet: boolean; apiKey: string | null }> {
  return fetchApi(`/settings/openrouter-api-key`, {}, authToken);
}

// Function to remove the OpenRouter API key
export async function removeOpenRouterApiKey(
  authToken: string
): Promise<{ message: string }> {
  return fetchApi(
    `/settings/openrouter-api-key`,
    {
      method: "DELETE",
    },
    authToken
  );
}

// Function to fetch the list of available OpenRouter models
// Define an interface for the expected OpenRouter model structure from the backend
export interface OpenRouterModel {
  id: string;
  name: string;
  description?: string;
  context_length?: number;
  // Add other fields if needed from the backend response (e.g., pricing)
}

export async function getOpenRouterModels(
  authToken: string
): Promise<OpenRouterModel[]> {
  return fetchApi<OpenRouterModel[]>(
    "/settings/openrouter-models",
    { method: "GET" },
    authToken
  );
}

// --- NEW Function to Update Architect Settings for a Project ---
export async function updateArchitectSettings(
  projectId: string,
  enabled: boolean,
  authToken: string
): Promise<{ message: string; project: unknown }> {
  // Assuming backend returns project details
  return fetchApi<{ message: string; project: unknown }>(
    `/projects/${projectId}/settings/architect`, // Correct endpoint path
    {
      method: "PUT",
      body: JSON.stringify({ enabled: enabled }), // Send the boolean flag
    },
    authToken
  );
}

export async function saveAnthropicApiKey(
  apiKey: string,
  authToken: string
): Promise<{ message: string }> {
  return fetchApi(
    `/settings/anthropic-api-key`,
    {
      method: "POST",
      body: JSON.stringify({ anthropicApiKey: apiKey }),
    },
    authToken
  );
}

export async function checkAnthropicApiKey(
  authToken: string
): Promise<{ isSet: boolean; apiKey: string | null }> {
  return fetchApi(`/settings/anthropic-api-key`, {}, authToken);
}

export async function removeAnthropicApiKey(
  authToken: string
): Promise<{ message: string }> {
  return fetchApi(
    `/settings/anthropic-api-key`,
    {
      method: "DELETE",
    },
    authToken
  );
}

export async function saveOpenAIApiKey(
  apiKey: string,
  authToken: string
): Promise<{ message: string }> {
  return fetchApi(
    `/settings/openai-api-key`,
    {
      method: "POST",
      body: JSON.stringify({ openAIApiKey: apiKey }),
    },
    authToken
  );
}

export async function checkOpenAIApiKey(
  authToken: string
): Promise<{ isSet: boolean; apiKey: string | null }> {
  return fetchApi(`/settings/openai-api-key`, {}, authToken);
}

export async function removeOpenAIApiKey(
  authToken: string
): Promise<{ message: string }> {
  return fetchApi(
    `/settings/openai-api-key`,
    {
      method: "DELETE",
    },
    authToken
  );
}

export async function extractTextFromFile(
  projectId: string,
  file: File,
  authToken: string
): Promise<{ text: string; filename: string }> {
  const formData = new FormData();
  formData.append("file", file);

  return fetchApi(
    `/projects/${projectId}/knowledge-base/extract-text`,
    {
      method: "POST",
      body: formData,
    },
    authToken
  );
}
