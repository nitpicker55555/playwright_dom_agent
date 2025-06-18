import { chromium } from 'playwright';

/**
 * Get snapshot using Playwright's internal _snapshotForAI method
 * This method is available as an internal API on the page object
 */
async function getSnapshotForAI(url, options = {}) {
  const browser = await chromium.launch({ 
    headless: options.headless !== false 
  });
  
  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    
    // Navigate to the URL with faster loading
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
    
    // Optimized wait - shorter timeout for network idle
    await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {
      console.log('Network idle timeout, proceeding anyway...');
    });
    
    // Use the internal _snapshotForAI method
    // This is an internal Playwright method available on the page object
    try {
      const snapshot = await page._snapshotForAI();
      
      // Try to add aria-ref attributes to elements based on the snapshot
      await addAriaRefAttributes(page, snapshot);
      
      return snapshot;
    } catch (error) {
      // If internal method is not available, try alternative approaches
      console.error('Internal _snapshotForAI method failed:', error.message);
      
      // Try to get a basic accessibility tree as fallback
      const accessibilitySnapshot = await page.accessibility.snapshot();
      if (accessibilitySnapshot) {
        // Convert accessibility snapshot to simple YAML-like format
        const refMapping = new Map();
        const formattedSnapshot = formatAccessibilitySnapshot(accessibilitySnapshot, 0, page, refMapping);
        
        // Add aria-ref attributes based on mapping
        await addAriaRefFromMapping(page, refMapping);
        
        return formattedSnapshot;
      }
      
      throw new Error('_snapshotForAI method not available and no fallback succeeded');
    }
    
  } finally {
    await browser.close();
  }
}

/**
 * Convert accessibility snapshot to simple YAML-like format and add aria-ref attributes to elements
 */
function formatAccessibilitySnapshot(snapshot, level = 0, page = null, refMapping = null) {
  if (!snapshot) return '';
  
  // Initialize ref mapping on first call
  if (refMapping === null) {
    refMapping = new Map();
  }
  
  const indent = '  '.repeat(level);
  let result = '';
  
  if (snapshot.role) {
    let line = `${indent}- ${snapshot.role}`;
    let refId = null;
    
    if (snapshot.name) {
      line += ` "${snapshot.name}"`;
      // Generate a simple ref for elements with names
      refId = `e${Math.abs(simpleHash(snapshot.name)) % 1000}`;
      line += ` [ref=${refId}]`;
      
      // Store mapping for later DOM attribute addition
      if (page && refMapping) {
        refMapping.set(refId, {
          role: snapshot.role,
          name: snapshot.name,
          selector: getElementSelector(snapshot)
        });
      }
    } else if (level === 0) {
      // Add ref for root element even without name
      refId = 'e1';
      line += ` [ref=${refId}]`;
    }
    
    result += line + '\n';
  }
  
  if (snapshot.children) {
    for (const child of snapshot.children) {
      result += formatAccessibilitySnapshot(child, level + 1, page, refMapping);
    }
  }
  
  return result;
}

/**
 * Generate CSS selector from accessibility node
 */
function getElementSelector(snapshot) {
  // Try to generate a reasonable selector based on accessibility info
  if (snapshot.name) {
    // Try by text content first
    const escapedName = snapshot.name.replace(/"/g, '\\"');
    return `text="${escapedName}"`;
  }
  
  // Fallback to role-based selector
  if (snapshot.role) {
    return `[role="${snapshot.role}"]`;
  }
  
  return null;
}

/**
 * Add aria-ref attributes to DOM elements based on snapshot
 */
async function addAriaRefAttributes(page, snapshot) {
  try {
    // Parse the snapshot text to extract ref mappings
    const lines = snapshot.split('\n');
    const refMappings = [];
    
    for (const line of lines) {
      // Match lines like "- button "Search" [ref=e123]"
      const match = line.match(/- (\w+)\s+"([^"]+)"\s+\[ref=([^\]]+)\]/);
      if (match) {
        const [, role, text, ref] = match;
        refMappings.push({ role, text, ref });
      }
    }
    
    // Add aria-ref attributes to matching elements
    await page.evaluate((mappings) => {
      for (const mapping of mappings) {
        // Try to find elements by text content
        const elements = Array.from(document.querySelectorAll('*')).filter(el => {
          const text = el.textContent?.trim();
          return text && text.includes(mapping.text.substring(0, 20)); // Partial match
        });
        
        // If found, add aria-ref to the first matching element
        if (elements.length > 0) {
          const element = elements[0];
          element.setAttribute('aria-ref', mapping.ref);
        }
      }
    }, refMappings);
    
  } catch (error) {
    console.error('Error adding aria-ref attributes:', error);
  }
}

/**
 * Add aria-ref attributes based on ref mapping
 */
async function addAriaRefFromMapping(page, refMapping) {
  try {
    const mappingArray = Array.from(refMapping.entries()).map(([ref, info]) => ({
      ref,
      ...info
    }));
    
    await page.evaluate((mappings) => {
      for (const mapping of mappings) {
        // Try to find elements by text content
        if (mapping.name) {
          const elements = Array.from(document.querySelectorAll('*')).filter(el => {
            const text = el.textContent?.trim();
            return text && text.includes(mapping.name.substring(0, 20)); // Partial match
          });
          
          // If found, add aria-ref to the first matching element
          if (elements.length > 0) {
            const element = elements[0];
            element.setAttribute('aria-ref', mapping.ref);
          }
        }
      }
    }, mappingArray);
    
  } catch (error) {
    console.error('Error adding aria-ref from mapping:', error);
  }
}

// Simple hash function for strings
function simpleHash(str) {
  let hash = 0;
  if (str.length === 0) return hash;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash);
}

/**
 * Get snapshot from an existing CDP session
 */
async function getSnapshotFromCDP(cdpEndpoint) {
  const browser = await chromium.connectOverCDP(cdpEndpoint);
  
  try {
    const contexts = browser.contexts();
    if (contexts.length === 0) {
      throw new Error('No browser contexts found');
    }
    
    const context = contexts[0];
    const pages = context.pages();
    if (pages.length === 0) {
      throw new Error('No pages found');
    }
    
    const page = pages[0];
    
    // Try the internal method first
    try {
      const snapshot = await page._snapshotForAI();
      return snapshot;
    } catch (error) {
      // Fallback to accessibility snapshot
      const accessibilitySnapshot = await page.accessibility.snapshot();
      if (accessibilitySnapshot) {
        return formatAccessibilitySnapshot(accessibilitySnapshot);
      }
      
      throw new Error('_snapshotForAI method not available and no fallback succeeded');
    }
    
  } finally {
    await browser.close();
  }
}

// Command line interface
if (process.argv.length > 2) {
  const command = process.argv[2];
  
  if (command === 'snapshot') {
    const url = process.argv[3];
    if (!url) {
      console.error('Usage: node snapshot_helper.js snapshot <url>');
      process.exit(1);
    }
    
    getSnapshotForAI(url)
      .then(snapshot => {
        console.log(JSON.stringify({ success: true, snapshot }));
      })
      .catch(error => {
        console.log(JSON.stringify({ success: false, error: error.message }));
      });
      
  } else if (command === 'snapshot-cdp') {
    const cdpEndpoint = process.argv[3];
    if (!cdpEndpoint) {
      console.error('Usage: node snapshot_helper.js snapshot-cdp <cdp-endpoint>');
      process.exit(1);
    }
    
    getSnapshotFromCDP(cdpEndpoint)
      .then(snapshot => {
        console.log(JSON.stringify({ success: true, snapshot }));
      })
      .catch(error => {
        console.log(JSON.stringify({ success: false, error: error.message }));
      });
  } else {
    console.error('Unknown command:', command);
    console.error('Available commands: snapshot, snapshot-cdp');
    process.exit(1);
  }
}

export { getSnapshotForAI, getSnapshotFromCDP }; 