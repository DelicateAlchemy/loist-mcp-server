#!/usr/bin/env node
/**
 * Enhanced MCP Test Results Validator
 * Validates MCP protocol compliance, error format consistency, and performance metrics
 */

const fs = require('fs');
const path = require('path');

// Expected error codes from src/error_utils.py
const EXPECTED_ERROR_CODES = [
    'AUDIO_PROCESSING_FAILED',
    'STORAGE_ERROR', 
    'VALIDATION_ERROR',
    'RESOURCE_NOT_FOUND',
    'TIMEOUT',
    'AUTHENTICATION_FAILED',
    'RATE_LIMIT_EXCEEDED',
    'EXTERNAL_SERVICE_ERROR',
    'INTERNAL_ERROR',
    'INVALID_QUERY',
    'DATABASE_ERROR'
];

// Performance thresholds (in seconds)
const PERFORMANCE_THRESHOLDS = {
    health_check: 2.0,
    get_audio_metadata: 1.0,
    search_library: 3.0,
    resource_access: 2.0
};

function validateJSONRPCResponse(response) {
    const errors = [];
    
    try {
        const parsed = JSON.parse(response);
        
        // Check JSON-RPC 2.0 compliance
        if (parsed.jsonrpc !== '2.0') {
            errors.push('Missing or invalid jsonrpc version');
        }
        
        if (!parsed.id && parsed.id !== 0) {
            errors.push('Missing request id');
        }
        
        // Check for result or error (but not both)
        const hasResult = 'result' in parsed;
        const hasError = 'error' in parsed;
        
        if (!hasResult && !hasError) {
            errors.push('Response must have either result or error');
        }
        
        if (hasResult && hasError) {
            errors.push('Response cannot have both result and error');
        }
        
        // Validate error format if present
        if (hasError) {
            if (typeof parsed.error.code !== 'number') {
                errors.push('Error code must be a number');
            }
            
            if (typeof parsed.error.message !== 'string') {
                errors.push('Error message must be a string');
            }
        }
        
        return { valid: errors.length === 0, errors, parsed };
    } catch (e) {
        return { valid: false, errors: ['Invalid JSON format'], parsed: null };
    }
}

function validateStandardizedErrorFormat(response) {
    const errors = [];
    
    try {
        const parsed = JSON.parse(response);
        
        // Check for standardized error format in structured content
        if (parsed.result && parsed.result.structuredContent) {
            const content = parsed.result.structuredContent;
            
            if (content.success === false) {
                // Validate error code
                if (!content.error || !EXPECTED_ERROR_CODES.includes(content.error)) {
                    errors.push(`Invalid or missing error code: ${content.error}`);
                }
                
                // Validate message
                if (!content.message || typeof content.message !== 'string') {
                    errors.push('Missing or invalid error message');
                }
                
                // Check for details object
                if (!content.details || typeof content.details !== 'object') {
                    errors.push('Missing or invalid error details');
                }
            }
        }
        
        return { valid: errors.length === 0, errors };
    } catch (e) {
        return { valid: false, errors: ['Invalid JSON format'] };
    }
}

function validateTestResults(resultsFile) {
    console.log(`🔍 Validating ${resultsFile}...`);
    
    if (!fs.existsSync(resultsFile)) {
        console.error(`❌ ${resultsFile} not found`);
        return { valid: false, summary: null };
    }
    
    let results;
    try {
        results = JSON.parse(fs.readFileSync(resultsFile, 'utf8'));
    } catch (e) {
        console.error(`❌ Invalid JSON in ${resultsFile}: ${e.message}`);
        return { valid: false, summary: null };
    }
    
    let hasErrors = false;
    const validationResults = {
        protocolCompliance: 0,
        errorFormatCompliance: 0,
        performanceIssues: 0,
        totalTests: results.tests ? results.tests.length : 0
    };
    
    console.log(`📊 Test Suite: ${results.testSuite}`);
    console.log(`⏱️  Duration: ${results.startTime} to ${results.endTime}`);
    console.log(`📈 Summary: ${results.summary?.total || 0} total, ${results.summary?.passed || 0} passed, ${results.summary?.failed || 0} failed`);
    
    if (results.tests) {
        for (const test of results.tests) {
            console.log(`\n🧪 Test: ${test.name} (${test.status})`);
            
            // Validate JSON-RPC protocol compliance
            if (test.response && test.response.includes('{"jsonrpc"')) {
                const jsonResponses = test.response.match(/\{"jsonrpc"[^}]+\}/g) || [];
                for (const jsonResp of jsonResponses) {
                    const validation = validateJSONRPCResponse(jsonResp);
                    if (!validation.valid) {
                        console.error(`   ❌ Protocol violation: ${validation.errors.join(', ')}`);
                        hasErrors = true;
                    } else {
                        validationResults.protocolCompliance++;
                        console.log(`   ✅ JSON-RPC protocol compliant`);
                    }
                    
                    // Validate standardized error format
                    const errorValidation = validateStandardizedErrorFormat(jsonResp);
                    if (!errorValidation.valid && errorValidation.errors.length > 0) {
                        console.warn(`   ⚠️  Error format: ${errorValidation.errors.join(', ')}`);
                    } else if (validation.parsed && validation.parsed.result && validation.parsed.result.structuredContent && validation.parsed.result.structuredContent.success === false) {
                        validationResults.errorFormatCompliance++;
                        console.log(`   ✅ Standardized error format compliant`);
                    }
                }
            }
            
            // Validate performance
            if (test.duration && typeof test.duration === 'number') {
                const threshold = PERFORMANCE_THRESHOLDS[test.name] || PERFORMANCE_THRESHOLDS.resource_access;
                if (test.duration > threshold) {
                    console.warn(`   ⚠️  Performance: ${test.duration}s exceeds threshold ${threshold}s`);
                    validationResults.performanceIssues++;
                } else {
                    console.log(`   ✅ Performance: ${test.duration}s within threshold`);
                }
            }
            
            // Check test status
            if (test.status === 'failed') {
                console.error(`   ❌ Test failed: ${test.errorMessage}`);
                hasErrors = true;
            }
        }
    }
    
    return { 
        valid: !hasErrors, 
        summary: results.summary,
        validation: validationResults
    };
}

function generateValidationReport(toolsResults, resourcesResults) {
    const report = {
        timestamp: new Date().toISOString(),
        overall: {
            status: (toolsResults.valid && resourcesResults.valid) ? 'PASSED' : 'FAILED',
            totalTests: (toolsResults.summary?.total || 0) + (resourcesResults.summary?.total || 0),
            totalPassed: (toolsResults.summary?.passed || 0) + (resourcesResults.summary?.passed || 0),
            totalFailed: (toolsResults.summary?.failed || 0) + (resourcesResults.summary?.failed || 0)
        },
        tools: toolsResults,
        resources: resourcesResults,
        compliance: {
            protocolCompliance: (toolsResults.validation?.protocolCompliance || 0) + (resourcesResults.validation?.protocolCompliance || 0),
            errorFormatCompliance: (toolsResults.validation?.errorFormatCompliance || 0) + (resourcesResults.validation?.errorFormatCompliance || 0),
            performanceIssues: (toolsResults.validation?.performanceIssues || 0) + (resourcesResults.validation?.performanceIssues || 0)
        }
    };
    
    fs.writeFileSync('mcp_validation_report.json', JSON.stringify(report, null, 2));
    return report;
}

function main() {
    console.log('🔍 MCP Test Results Validation');
    console.log('================================');
    
    // Validate both test result files
    const toolsResults = validateTestResults('mcp_tools_results.json');
    const resourcesResults = validateTestResults('mcp_resources_results.json');
    
    // Generate comprehensive report
    const report = generateValidationReport(toolsResults, resourcesResults);
    
    console.log('\n📋 Validation Summary');
    console.log('====================');
    console.log(`Overall Status: ${report.overall.status}`);
    console.log(`Total Tests: ${report.overall.totalTests}`);
    console.log(`Passed: ${report.overall.totalPassed}`);
    console.log(`Failed: ${report.overall.totalFailed}`);
    console.log(`Protocol Compliance: ${report.compliance.protocolCompliance} responses`);
    console.log(`Error Format Compliance: ${report.compliance.errorFormatCompliance} errors`);
    console.log(`Performance Issues: ${report.compliance.performanceIssues} tests`);
    
    console.log(`\n📄 Full report saved to: mcp_validation_report.json`);
    
    if (report.overall.status === 'FAILED') {
        console.error('\n❌ MCP validation failed!');
        process.exit(1);
    } else {
        console.log('\n✅ All MCP validations passed!');
        process.exit(0);
    }
}

if (require.main === module) {
    main();
}

module.exports = { validateJSONRPCResponse, validateStandardizedErrorFormat, validateTestResults };
