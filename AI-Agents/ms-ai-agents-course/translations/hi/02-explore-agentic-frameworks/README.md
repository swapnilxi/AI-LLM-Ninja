<!--
CO_OP_TRANSLATOR_METADATA:
{
  "original_hash": "d3ceafa2939ede602b96d6bd412c5cbf",
  "translation_date": "2025-04-05T19:44:24+00:00",
  "source_file": "02-explore-agentic-frameworks\\README.md",
  "language_code": "hi"
}
-->
[![AI एजेंट फ्रेमवर्क्स का अन्वेषण](../../../translated_images/lesson-2-thumbnail.807a3a4fc57057096d10678bf84638d17d50c50239014e75a7708731a33bb802.hi.png)](https://youtu.be/ODwF-EZo_O8?si=1xoy_B9RNQfrYdF7)

> _(ऊपर दी गई छवि पर क्लिक करें इस पाठ का वीडियो देखने के लिए)_

# AI एजेंट फ्रेमवर्क्स का अन्वेषण

AI एजेंट फ्रेमवर्क्स सॉफ़्टवेयर प्लेटफ़ॉर्म हैं जो AI एजेंट्स को बनाने, तैनात करने और प्रबंधित करने की प्रक्रिया को सरल बनाते हैं। ये फ्रेमवर्क्स डेवलपर्स को पूर्व-निर्मित घटक, अमूर्तता और उपकरण प्रदान करते हैं जो जटिल AI सिस्टम के विकास को सुव्यवस्थित करते हैं।

ये फ्रेमवर्क्स डेवलपर्स को AI एजेंट विकास में आम चुनौतियों के लिए मानकीकृत दृष्टिकोण प्रदान करके उनके अनुप्रयोगों के अद्वितीय पहलुओं पर ध्यान केंद्रित करने में मदद करते हैं। वे AI सिस्टम बनाने में स्केलेबिलिटी, पहुंच और दक्षता को बढ़ाते हैं।

## परिचय 

इस पाठ में शामिल हैं:

- AI एजेंट फ्रेमवर्क्स क्या हैं और वे डेवलपर्स को क्या हासिल करने में सक्षम बनाते हैं?
- टीम इनका उपयोग अपने एजेंट की क्षमताओं को तेजी से प्रोटोटाइप, दोहराने और सुधारने के लिए कैसे कर सकती हैं?
- Microsoft द्वारा बनाए गए फ्रेमवर्क्स और टूल्स के बीच क्या अंतर हैं?
- क्या मैं अपने मौजूदा Azure इकोसिस्टम टूल्स को सीधे एकीकृत कर सकता हूं, या मुझे स्टैंडअलोन समाधान चाहिए?
- Azure AI Agents सेवा क्या है और यह मेरी कैसे मदद कर रही है?

## सीखने के लक्ष्य

इस पाठ के लक्ष्य हैं:

- AI विकास में AI एजेंट फ्रेमवर्क्स की भूमिका को समझना।
- बुद्धिमान एजेंट्स बनाने के लिए AI एजेंट फ्रेमवर्क्स का उपयोग कैसे करें।
- AI एजेंट फ्रेमवर्क्स द्वारा सक्षम की गई प्रमुख क्षमताएं।
- AutoGen, Semantic Kernel और Azure AI Agent Service के बीच अंतर।

## AI एजेंट फ्रेमवर्क्स क्या हैं और वे डेवलपर्स को क्या करने में सक्षम बनाते हैं?

पारंपरिक AI फ्रेमवर्क्स आपके ऐप्स में AI को एकीकृत करने और इन ऐप्स को निम्नलिखित तरीकों से बेहतर बनाने में मदद कर सकते हैं:

- **पर्सनलाइजेशन**: AI उपयोगकर्ता व्यवहार और प्राथमिकताओं का विश्लेषण करके व्यक्तिगत सिफारिशें, सामग्री और अनुभव प्रदान कर सकता है।  
उदाहरण: Netflix जैसी स्ट्रीमिंग सेवाएं उपयोगकर्ता के देखने के इतिहास के आधार पर फिल्में और शो सुझाने के लिए AI का उपयोग करती हैं, जिससे उपयोगकर्ता की व्यस्तता और संतुष्टि बढ़ती है।  
- **स्वचालन और दक्षता**: AI दोहराए जाने वाले कार्यों को स्वचालित कर सकता है, वर्कफ़्लो को सुव्यवस्थित कर सकता है और परिचालन दक्षता में सुधार कर सकता है।  
उदाहरण: ग्राहक सेवा ऐप्स सामान्य पूछताछ को संभालने के लिए AI-संचालित चैटबॉट्स का उपयोग करते हैं, प्रतिक्रिया समय को कम करते हैं और मानव एजेंट्स को अधिक जटिल मुद्दों के लिए मुक्त करते हैं।  
- **उन्नत उपयोगकर्ता अनुभव**: AI वॉयस रिकग्निशन, प्राकृतिक भाषा प्रसंस्करण और प्रेडिक्टिव टेक्स्ट जैसे बुद्धिमान फीचर्स प्रदान करके समग्र उपयोगकर्ता अनुभव को बेहतर बना सकता है।  
उदाहरण: Siri और Google Assistant जैसे वर्चुअल असिस्टेंट्स AI का उपयोग करके वॉयस कमांड को समझते और जवाब देते हैं, जिससे उपयोगकर्ताओं के लिए अपने डिवाइस के साथ इंटरैक्ट करना आसान हो जाता है।  

### यह सब अच्छा लगता है, तो फिर AI एजेंट फ्रेमवर्क की आवश्यकता क्यों है?

AI एजेंट फ्रेमवर्क्स केवल AI फ्रेमवर्क्स से अधिक का प्रतिनिधित्व करते हैं। इन्हें बुद्धिमान एजेंट्स बनाने के लिए डिज़ाइन किया गया है जो उपयोगकर्ताओं, अन्य एजेंट्स और पर्यावरण के साथ बातचीत कर सकते हैं ताकि विशिष्ट लक्ष्यों को प्राप्त किया जा सके। ये एजेंट्स स्वायत्त व्यवहार प्रदर्शित कर सकते हैं, निर्णय ले सकते हैं और बदलती परिस्थितियों के अनुकूल हो सकते हैं। आइए AI एजेंट फ्रेमवर्क्स द्वारा सक्षम कुछ प्रमुख क्षमताओं पर नज़र डालें:

- **एजेंट सहयोग और समन्वय**: कई AI एजेंट्स बनाने में सक्षम बनाना जो एक साथ काम कर सकते हैं, संवाद कर सकते हैं और जटिल कार्यों को हल करने के लिए समन्वय कर सकते हैं।  
- **कार्य स्वचालन और प्रबंधन**: मल्टी-स्टेप वर्कफ़्लो, कार्य प्रतिनिधि और एजेंट्स के बीच गतिशील कार्य प्रबंधन को स्वचालित करने के लिए तंत्र प्रदान करना।  
- **प्रासंगिक समझ और अनुकूलन**: एजेंट्स को संदर्भ को समझने, बदलते वातावरण के अनुकूल होने और वास्तविक समय की जानकारी के आधार पर निर्णय लेने की क्षमता प्रदान करना।  

संक्षेप में, एजेंट्स आपको अधिक करने की अनुमति देते हैं, स्वचालन को अगले स्तर पर ले जाने, अधिक बुद्धिमान सिस्टम बनाने और अपने पर्यावरण से सीखने और अनुकूलित करने की क्षमता प्रदान करते हैं।

## एजेंट की क्षमताओं को जल्दी प्रोटोटाइप, दोहराने और सुधारने के लिए कैसे करें?

यह एक तेजी से बदलता हुआ परिदृश्य है, लेकिन अधिकांश AI एजेंट फ्रेमवर्क्स में कुछ सामान्य बातें हैं जो आपको जल्दी प्रोटोटाइप और दोहराने में मदद कर सकती हैं, जैसे मॉड्यूल घटक, सहयोगी उपकरण और वास्तविक समय सीखना। आइए इनमें गहराई से जाएं:

- **मॉड्यूल घटकों का उपयोग करें**: AI SDKs पूर्व-निर्मित घटक प्रदान करते हैं जैसे AI और मेमोरी कनेक्टर्स, प्राकृतिक भाषा या कोड प्लगइन्स का उपयोग करके फंक्शन कॉलिंग, प्रॉम्प्ट टेम्पलेट्स और बहुत कुछ।  
- **सहयोगी उपकरणों का लाभ उठाएं**: विशिष्ट भूमिकाओं और कार्यों के साथ एजेंट्स डिज़ाइन करें, जिससे उन्हें सहयोगात्मक वर्कफ़्लो का परीक्षण और परिष्कृत करने की अनुमति मिलती है।  
- **वास्तविक समय में सीखें**: फीडबैक लूप्स को लागू करें जहां एजेंट्स इंटरैक्शन से सीखते हैं और गतिशील रूप से अपने व्यवहार को समायोजित करते हैं।  

### मॉड्यूल घटकों का उपयोग करें

Microsoft Semantic Kernel और LangChain जैसे SDKs पूर्व-निर्मित घटक प्रदान करते हैं जैसे AI कनेक्टर्स, प्रॉम्प्ट टेम्पलेट्स और मेमोरी प्रबंधन।  

**टीमें इसका उपयोग कैसे कर सकती हैं**: टीमें इन घटकों को जल्दी से इकट्ठा करके एक कार्यात्मक प्रोटोटाइप बना सकती हैं बिना शुरुआत से शुरू किए, जिससे तेजी से प्रयोग और दोहराव संभव हो सके।  

**यह व्यवहार में कैसे काम करता है**: आप उपयोगकर्ता इनपुट से जानकारी निकालने के लिए एक पूर्व-निर्मित पार्सर का उपयोग कर सकते हैं, डेटा स्टोर और पुनर्प्राप्त करने के लिए एक मेमोरी मॉड्यूल और उपयोगकर्ताओं के साथ बातचीत करने के लिए एक प्रॉम्प्ट जनरेटर, यह सब बिना इन घटकों को शुरुआत से बनाने के।  

**उदाहरण कोड**. आइए देखें कि कैसे आप Semantic Kernel Python और .Net के साथ एक पूर्व-निर्मित AI कनेक्टर का उपयोग कर सकते हैं जो ऑटो-फंक्शन कॉलिंग का उपयोग करता है ताकि मॉडल उपयोगकर्ता इनपुट का जवाब दे सके:  

``` python
# Semantic Kernel Python Example

import asyncio
from typing import Annotated

from semantic_kernel.connectors.ai import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, AzureChatPromptExecutionSettings
from semantic_kernel.contents import ChatHistory
from semantic_kernel.functions import kernel_function
from semantic_kernel.kernel import Kernel

# Define a ChatHistory object to hold the conversation's context
chat_history = ChatHistory()
chat_history.add_user_message("I'd like to go to New York on January 1, 2025")


# Define a sample plugin that contains the function to book travel
class BookTravelPlugin:
    """A Sample Book Travel Plugin"""

    @kernel_function(name="book_flight", description="Book travel given location and date")
    async def book_flight(
        self, date: Annotated[str, "The date of travel"], location: Annotated[str, "The location to travel to"]
    ) -> str:
        return f"Travel was booked to {location} on {date}"

# Create the Kernel
kernel = Kernel()

# Add the sample plugin to the Kernel object
kernel.add_plugin(BookTravelPlugin(), plugin_name="book_travel")

# Define the Azure OpenAI AI Connector
chat_service = AzureChatCompletion(
    deployment_name="YOUR_DEPLOYMENT_NAME", 
    api_key="YOUR_API_KEY", 
    endpoint="https://<your-resource>.azure.openai.com/",
)

# Define the request settings to configure the model with auto-function calling
request_settings = AzureChatPromptExecutionSettings(function_choice_behavior=FunctionChoiceBehavior.Auto())


async def main():
    # Make the request to the model for the given chat history and request settings
    # The Kernel contains the sample that the model will request to invoke
    response = await chat_service.get_chat_message_content(
        chat_history=chat_history, settings=request_settings, kernel=kernel
    )
    assert response is not None

    """
    Note: In the auto function calling process, the model determines it can invoke the 
    `BookTravelPlugin` using the `book_flight` function, supplying the necessary arguments. 
    
    For example:

    "tool_calls": [
        {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "BookTravelPlugin-book_flight",
                "arguments": "{'location': 'New York', 'date': '2025-01-01'}"
            }
        }
    ]

    Since the location and date arguments are required (as defined by the kernel function), if the 
    model lacks either, it will prompt the user to provide them. For instance:

    User: Book me a flight to New York.
    Model: Sure, I'd love to help you book a flight. Could you please specify the date?
    User: I want to travel on January 1, 2025.
    Model: Your flight to New York on January 1, 2025, has been successfully booked. Safe travels!
    """

    print(f"`{response}`")
    # Example AI Model Response: `Your flight to New York on January 1, 2025, has been successfully booked. Safe travels! ✈️🗽`

    # Add the model's response to our chat history context
    chat_history.add_assistant_message(response.content)


if __name__ == "__main__":
    asyncio.run(main())
```  
```csharp
// Semantic Kernel C# example

using Microsoft.SemanticKernel;
using Microsoft.SemanticKernel.ChatCompletion;
using System.ComponentModel;
using Microsoft.SemanticKernel.Connectors.AzureOpenAI;

ChatHistory chatHistory = [];
chatHistory.AddUserMessage("I'd like to go to New York on January 1, 2025");

var kernelBuilder = Kernel.CreateBuilder();
kernelBuilder.AddAzureOpenAIChatCompletion(
    deploymentName: "NAME_OF_YOUR_DEPLOYMENT",
    apiKey: "YOUR_API_KEY",
    endpoint: "YOUR_AZURE_ENDPOINT"
);
kernelBuilder.Plugins.AddFromType<BookTravelPlugin>("BookTravel"); 
var kernel = kernelBuilder.Build();

var settings = new AzureOpenAIPromptExecutionSettings()
{
    FunctionChoiceBehavior = FunctionChoiceBehavior.Auto()
};

var chatCompletion = kernel.GetRequiredService<IChatCompletionService>();

var response = await chatCompletion.GetChatMessageContentAsync(chatHistory, settings, kernel);

/*
Behind the scenes, the model recognizes the tool to call, what arguments it already has (location) and (date)
{

"tool_calls": [
    {
        "id": "call_abc123",
        "type": "function",
        "function": {
            "name": "BookTravelPlugin-book_flight",
            "arguments": "{'location': 'New York', 'date': '2025-01-01'}"
        }
    }
]
*/

Console.WriteLine(response.Content);
chatHistory.AddMessage(response!.Role, response!.Content!);

// Example AI Model Response: Your flight to New York on January 1, 2025, has been successfully booked. Safe travels! ✈️🗽

// Define a plugin that contains the function to book travel
public class BookTravelPlugin
{
    [KernelFunction("book_flight")]
    [Description("Book travel given location and date")]
    public async Task<string> BookFlight(DateTime date, string location)
    {
        return await Task.FromResult( $"Travel was booked to {location} on {date}");
    }
}
```  

इस उदाहरण से आप देख सकते हैं कि कैसे आप उपयोगकर्ता इनपुट से मुख्य जानकारी निकालने के लिए एक पूर्व-निर्मित पार्सर का लाभ उठा सकते हैं, जैसे कि फ्लाइट बुकिंग अनुरोध की उत्पत्ति, गंतव्य और तारीख। इस मॉड्यूल दृष्टिकोण से आप उच्च-स्तरीय तर्क पर ध्यान केंद्रित कर सकते हैं।  

### सहयोगी उपकरणों का लाभ उठाएं

CrewAI, Microsoft AutoGen और Semantic Kernel जैसे फ्रेमवर्क्स कई एजेंट्स बनाने की सुविधा प्रदान करते हैं जो एक साथ काम कर सकते हैं।  

**टीमें इसका उपयोग कैसे कर सकती हैं**: टीमें विशिष्ट भूमिकाओं और कार्यों के साथ एजेंट्स डिज़ाइन कर सकती हैं, जिससे उन्हें सहयोगात्मक वर्कफ़्लो का परीक्षण और परिष्कृत करने और समग्र सिस्टम दक्षता में सुधार करने की अनुमति मिलती है।  

**यह व्यवहार में कैसे काम करता है**: आप एजेंट्स की एक टीम बना सकते हैं जहां प्रत्येक एजेंट का एक विशेष कार्य होता है, जैसे डेटा पुनर्प्राप्ति, विश्लेषण या निर्णय लेना। ये एजेंट्स एक सामान्य लक्ष्य प्राप्त करने के लिए संवाद और जानकारी साझा कर सकते हैं, जैसे उपयोगकर्ता क्वेरी का उत्तर देना या कार्य पूरा करना।  

**उदाहरण कोड (AutoGen)**:  

```python
# creating agents, then create a round robin schedule where they can work together, in this case in order

# Data Retrieval Agent
# Data Analysis Agent
# Decision Making Agent

agent_retrieve = AssistantAgent(
    name="dataretrieval",
    model_client=model_client,
    tools=[retrieve_tool],
    system_message="Use tools to solve tasks."
)

agent_analyze = AssistantAgent(
    name="dataanalysis",
    model_client=model_client,
    tools=[analyze_tool],
    system_message="Use tools to solve tasks."
)

# conversation ends when user says "APPROVE"
termination = TextMentionTermination("APPROVE")

user_proxy = UserProxyAgent("user_proxy", input_func=input)

team = RoundRobinGroupChat([agent_retrieve, agent_analyze, user_proxy], termination_condition=termination)

stream = team.run_stream(task="Analyze data", max_turns=10)
# Use asyncio.run(...) when running in a script.
await Console(stream)
```  

पिछले कोड में आप देख सकते हैं कि कैसे आप एक कार्य बना सकते हैं जिसमें कई एजेंट्स डेटा का विश्लेषण करने के लिए एक साथ काम करते हैं। प्रत्येक एजेंट एक विशिष्ट कार्य करता है, और एजेंट्स को समन्वयित करके कार्य को वांछित परिणाम प्राप्त करने के लिए निष्पादित किया जाता है। विशेष भूमिकाओं वाले समर्पित एजेंट्स बनाकर, आप कार्य दक्षता और प्रदर्शन में सुधार कर सकते हैं।  

### वास्तविक समय में सीखें

उन्नत फ्रेमवर्क्स वास्तविक समय संदर्भ समझ और अनुकूलन के लिए क्षमताएं प्रदान करते हैं।  

**टीमें इसका उपयोग कैसे कर सकती हैं**: टीमें फीडबैक लूप्स लागू कर सकती हैं जहां एजेंट्स इंटरैक्शन से सीखते हैं और गतिशील रूप से अपने व्यवहार को समायोजित करते हैं, जिससे क्षमताओं में निरंतर सुधार और परिष्करण होता है।  

**यह व्यवहार में कैसे काम करता है**: एजेंट्स उपयोगकर्ता फीडबैक, पर्यावरणीय डेटा और कार्य परिणामों का विश्लेषण कर सकते हैं ताकि अपने ज्ञान आधार को अपडेट किया जा सके, निर्णय लेने वाले एल्गोरिदम को समायोजित किया जा सके, और समय के साथ प्रदर्शन में सुधार किया जा सके। यह पुनरावृत्त सीखने की प्रक्रिया एजेंट्स को बदलती परिस्थितियों और उपयोगकर्ता प्राथमिकताओं के अनुकूल बनाने में सक्षम बनाती है, जिससे समग्र सिस्टम प्रभावशीलता बढ़ती है।  

## AutoGen, Semantic Kernel और Azure AI Agent Service के फ्रेमवर्क्स में क्या अंतर है?

इन फ्रेमवर्क्स की तुलना करने के कई तरीके हैं, लेकिन आइए उनके डिज़ाइन, क्षमताओं और लक्षित उपयोग मामलों के संदर्भ में कुछ प्रमुख अंतरों को देखें:  

## AutoGen

AutoGen Microsoft Research's AI Frontiers Lab द्वारा विकसित एक ओपन-सोर्स फ्रेमवर्क है। यह इवेंट-ड्रिवन, वितरित *एजेंटिक* अनुप्रयोगों पर केंद्रित है, जिससे कई LLMs और SLMs, टूल्स और उन्नत मल्टी-एजेंट डिज़ाइन पैटर्न सक्षम होते हैं।  

AutoGen एजेंट्स के मुख्य विचार के चारों ओर बनाया गया है, जो स्वायत्त संस्थाएं हैं जो अपने पर्यावरण को समझ सकती हैं, निर्णय ले सकती हैं और विशिष्ट लक्ष्यों को प्राप्त करने के लिए कार्रवाई कर सकती हैं। एजेंट्स असिंक्रोनस संदेशों के माध्यम से संवाद करते हैं, जिससे वे स्वतंत्र रूप से और समानांतर में काम कर सकते हैं, सिस्टम की स्केलेबिलिटी और उत्तरदायित्व को बढ़ाते हैं।
मॉड्यूलरिटी, सहयोग, प्रक्रिया ऑर्केस्ट्रेशन | सुरक्षित, स्केलेबल, और लचीला AI एजेंट डिप्लॉयमेंट | इन फ्रेमवर्क्स के लिए आदर्श उपयोग केस क्या है?  

## क्या मैं अपने मौजूदा Azure इकोसिस्टम टूल्स को सीधे एकीकृत कर सकता हूं, या मुझे स्टैंडअलोन समाधान की आवश्यकता है?  
उत्तर है हां, आप अपने मौजूदा Azure इकोसिस्टम टूल्स को Azure AI Agent Service के साथ सीधे एकीकृत कर सकते हैं, खासकर क्योंकि इसे अन्य Azure सेवाओं के साथ सहजता से काम करने के लिए डिज़ाइन किया गया है। उदाहरण के लिए, आप Bing, Azure AI Search, और Azure Functions को एकीकृत कर सकते हैं। Azure AI Foundry के साथ भी गहरा एकीकरण उपलब्ध है।  

AutoGen और Semantic Kernel के लिए, आप Azure सेवाओं के साथ भी एकीकृत कर सकते हैं, लेकिन इसके लिए आपको अपने कोड से Azure सेवाओं को कॉल करने की आवश्यकता हो सकती है। एक और तरीका यह है कि आप Azure SDKs का उपयोग करके अपने एजेंट्स को Azure सेवाओं के साथ इंटरैक्ट कराएं।  

इसके अलावा, जैसा कि पहले उल्लेख किया गया था, आप AutoGen या Semantic Kernel में बनाए गए एजेंट्स के लिए Azure AI Agent Service को एक ऑर्केस्ट्रेटर के रूप में उपयोग कर सकते हैं, जो Azure इकोसिस्टम तक आसान पहुंच प्रदान करेगा।  

## संदर्भ  
-  

## पिछला पाठ  
[AI एजेंट्स और उनके उपयोग मामलों का परिचय](../01-intro-to-ai-agents/README.md)  

## अगला पाठ  
[एजेंटिक डिज़ाइन पैटर्न को समझना](../03-agentic-design-patterns/README.md)  

**अस्वीकरण**:  
यह दस्तावेज़ AI अनुवाद सेवा [Co-op Translator](https://github.com/Azure/co-op-translator) का उपयोग करके अनुवादित किया गया है। जबकि हम सटीकता के लिए प्रयासरत हैं, कृपया ध्यान दें कि स्वचालित अनुवाद में त्रुटियाँ या गलतियाँ हो सकती हैं। मूल भाषा में मौजूद दस्तावेज़ को प्रामाणिक स्रोत माना जाना चाहिए। महत्वपूर्ण जानकारी के लिए, पेशेवर मानव अनुवाद की सिफारिश की जाती है। इस अनुवाद के उपयोग से उत्पन्न किसी भी गलतफहमी या गलत व्याख्या के लिए हम उत्तरदायी नहीं हैं।