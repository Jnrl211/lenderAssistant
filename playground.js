// Change of plans. This is too problematic, this website's API requests require Cookies and obfuscated authentication headers.
// Scrapping data the usual way will be simpler and quicker than reverse-engineering the API.

console.log("Test");

/** @type {Response} */
let requisitions = await fetch("https://api.[WEBSITE_DOMAIN_NAME].com/v2/investor/requisition_listings", {
    headers: {
        "Referer": "https://app.[WEBSITE_DOMAIN_NAME].com/",
        "Cookie": ""
    }
});

// This should return an array or an object... I should test it out putting this code into an execute_script call in the Selenium script.
/** @type {any} */
let requisitionsJSON = await requisitions.json();