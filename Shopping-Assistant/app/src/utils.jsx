
export const transformProfileOptions = (profileOptions) => {
  return profileOptions.map((option) => {
    // Convert to lowercase and replace spaces with underscores for the value
    const value = option.toLowerCase().replace(/ /g, "_");
    return { value: value, label: option };
  });
};


export function handleErrorResponse(buttonText, response) {
  if (response.message && response.message.startsWith("Error")) {
    const errorMessage = `${buttonText} - Message: ${response.message}. Please try again later.`;
    return errorMessage;
  }
  return "";
}
