const dropdown = document.querySelector('.version-picker .dropdown');
const dropdownMenu = dropdown ? dropdown.querySelector('.dropdown-menu') : null;

if (dropdown && dropdownMenu) {
    fetchVersions(dropdown, dropdownMenu).then((versions) => {
        if (versions.length > 1) {
            initializeVersionDropdown(dropdown, dropdownMenu);
        }
    });
}

/**
 * Initialize the dropdown functionality for version selection.
 * 
 * @param {Element} dropdown - The dropdown element.
 * @param {Element} dropdownMenu - The dropdown menu element.
 */
function initializeVersionDropdown(dropdown, dropdownMenu) {
    // Toggle the dropdown menu on click
    dropdown.addEventListener('click', function () {
        this.setAttribute('tabindex', 1);
        this.classList.toggle('active');
        dropdownMenu.style.display = (dropdownMenu.style.display === 'block') ? 'none' : 'block';
    });
  
    // Remove the 'active' class and hide the dropdown menu on focusout
    dropdown.addEventListener('focusout', function () {
        this.classList.remove('active');
        dropdownMenu.style.display = 'none';
    });
  
    // Handle item selection within the dropdown menu
    const dropdownMenuItems = dropdownMenu.querySelectorAll('li');    
    dropdownMenuItems.forEach(function (item) {
        item.addEventListener('click', function () {
            dropdownMenuItems.forEach(function (item) {
                item.classList.remove('active');
            });
            this.classList.add('active');
            dropdown.querySelector('span').textContent = this.textContent;
            dropdown.querySelector('input').value = this.getAttribute('id');

            window.location.href = changeVersion(window.location.href, this.textContent);
        });
    });
};

/**
 * This function fetches the available versions from a GitHub repository
 * and inserts them into the version picker.
 * 
 * @param {Element} dropdown - The dropdown element.
 * @param {Element} dropdownMenu - The dropdown menu element.
 * @returns {Promise<Array<string>>} A promise that resolves with an array of available versions.
 */
function fetchVersions(dropdown, dropdownMenu) {
    return new Promise((resolve) => {
        window.addEventListener("load", async () => {
            const currentVersion = window.SYNAPSE_VERSION || "latest";
            const fallbackVersions = [currentVersion];

            // Allow explicitly provided versions to avoid network requests.
            if (Array.isArray(window.SYNAPSE_VERSIONS) && window.SYNAPSE_VERSIONS.length > 0) {
                const versions = window.SYNAPSE_VERSIONS.slice().sort(sortVersions);
                renderVersions(dropdown, dropdownMenu, versions, currentVersion);
                resolve(versions);
                return;
            }

            // Optional API endpoint for dynamic version discovery.
            const versionTreeApi = window.SYNAPSE_VERSION_PICKER_API;
            if (!versionTreeApi) {
                renderVersions(dropdown, dropdownMenu, fallbackVersions, currentVersion);
                resolve(fallbackVersions);
                return;
            }

            try {
                const response = await fetch(versionTreeApi, { cache: "force-cache" });
                if (!response.ok) {
                    throw new Error(`Request failed with status ${response.status}`);
                }

                const resObject = await response.json();
                const excluded = ['dev-docs', 'v1.91.0', 'v1.80.0', 'v1.69.0'];
                const tree = Array.isArray(resObject.tree)
                    ? resObject.tree.filter(item => item.type === "tree" && !excluded.includes(item.path))
                    : [];

                const versions = tree
                    .map(item => item.path)
                    .filter(item => item === "develop" || item === "latest" || /^v\d+(\.\d+)+$/.test(item))
                    .sort(sortVersions);

                const finalVersions = versions.length > 0 ? versions : fallbackVersions;
                if (!finalVersions.includes(currentVersion)) {
                    finalVersions.unshift(currentVersion);
                }

                renderVersions(dropdown, dropdownMenu, finalVersions, currentVersion);
                resolve(finalVersions);
            } catch (ex) {
                console.warn("Failed to fetch version data; falling back to current version.", ex);
                renderVersions(dropdown, dropdownMenu, fallbackVersions, currentVersion);
                resolve(fallbackVersions);
            }
        }, { once: true });
    });
}

/**
 * Render available versions into the dropdown and set selected value.
 *
 * @param {Element} dropdown - The dropdown element.
 * @param {Element} dropdownMenu - The dropdown menu element.
 * @param {Array<string>} versions - Versions to render.
 * @param {string} currentVersion - Current docs version.
 */
function renderVersions(dropdown, dropdownMenu, versions, currentVersion) {
    dropdownMenu.innerHTML = "";

    versions.forEach((version) => {
        const li = document.createElement("li");
        li.textContent = version;
        li.id = version;

        if (currentVersion === version) {
            li.classList.add('active');
            dropdown.querySelector('span').textContent = version;
            dropdown.querySelector('input').value = version;
        }

        dropdownMenu.appendChild(li);
    });

    // Ensure label/input are always set, even if currentVersion was absent.
    if (!dropdown.querySelector('input').value && versions.length > 0) {
        dropdown.querySelector('span').textContent = versions[0];
        dropdown.querySelector('input').value = versions[0];
    }
}

/**
 * Custom sorting function to sort an array of version strings.
 *
 * @param {string} a - The first version string to compare.
 * @param {string} b - The second version string to compare.
 * @returns {number} - A negative number if a should come before b, a positive number if b should come before a, or 0 if they are equal.
 */
function sortVersions(a, b) {
    // Put 'develop' and 'latest' at the top
    if (a === 'develop' || a === 'latest') return -1;
    if (b === 'develop' || b === 'latest') return 1;

    // If any of the versions do not confrom to a semantic version string, they
    // will be sorted behind a valid version.
    const versionA = (a.match(/v(\d+(\.\d+)+)/) || [])[1]?.split('.') ?? '';
    const versionB = (b.match(/v(\d+(\.\d+)+)/) || [])[1]?.split('.') ?? '';

    for (let i = 0; i < Math.max(versionA.length, versionB.length); i++) {
        if (versionB[i] === undefined) {
            return -1;
        }
        if (versionA[i] === undefined) {
            return 1;
        }

        const partA = parseInt(versionA[i], 10);
        const partB = parseInt(versionB[i], 10);

        if (partA > partB) {
            return -1;
        } else if (partB > partA) {
            return 1;
        }
    }

    return 0;
}

/**
 * Change the version in a URL path.
 *
 * @param {string} url - The original URL to be modified.
 * @param {string} newVersion - The new version to replace the existing version in the URL.
 * @returns {string} The updated URL with the new version.
 */
function changeVersion(url, newVersion) {
    const parsedURL = new URL(url);
    const pathSegments = parsedURL.pathname.split('/');
  
    // Modify the version
    pathSegments[2] = newVersion;

    // Reconstruct the URL
    parsedURL.pathname = pathSegments.join('/');
  
    return parsedURL.href;
}
