/*******************************************************************************
 * verinice.veo
 * Copyright (C) 2025  SparksBM
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 ******************************************************************************/
package org.veo.rest;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.stream.Collectors;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import org.veo.core.entity.Asset;
import org.veo.core.entity.Control;
import org.veo.core.entity.Element;
import org.veo.core.entity.Person;
import org.veo.core.entity.Process;
import org.veo.core.entity.RiskAffected;
import org.veo.core.entity.Scope;
import org.veo.core.entity.Scenario;
import org.veo.core.entity.AbstractRisk;
import org.veo.core.entity.risk.RiskDefinitionRef;
import org.veo.core.entity.risk.DeterminedRisk;
import org.veo.core.entity.risk.Impact;
import org.veo.core.entity.risk.Probability;
import org.veo.core.entity.risk.RiskTreatmentOption;
import org.veo.core.entity.risk.RiskValues;
import org.veo.core.entity.compliance.ControlImplementation;
import org.veo.core.entity.compliance.RequirementImplementation;
import org.veo.core.entity.compliance.ReqImplRef;
import org.veo.core.entity.compliance.ImplementationStatus;
import org.veo.core.entity.ref.TypedId;
import org.veo.core.repository.PagingConfiguration;
import org.veo.core.usecase.asset.GetAssetUseCase;
import org.veo.core.usecase.base.GetElementUseCase;
import org.veo.core.usecase.compliance.GetControlImplementationsUseCase;
import org.veo.core.usecase.process.GetProcessUseCase;
import org.veo.core.usecase.scope.GetScopeUseCase;
import org.veo.core.repository.ScopeRepository;
import org.veo.core.UserAccessRights;
import org.veo.core.service.UserAccessRightsProvider;
import org.veo.rest.RestApplication;
import org.veo.core.entity.Domain;
import org.hibernate.Hibernate;

/**
 * REST controller for reporting functionality.
 * Provides standard reports metadata.
 */
@RestController
@RequestMapping("/api/reporting")
@SecurityRequirement(name = RestApplication.SECURITY_SCHEME_OAUTH)
public class ReportingController extends AbstractVeoController {
  
  @org.springframework.beans.factory.annotation.Autowired
  private GetScopeUseCase getScopeUseCase;
  
  @org.springframework.beans.factory.annotation.Autowired
  private GetAssetUseCase getAssetUseCase;
  
  @org.springframework.beans.factory.annotation.Autowired
  private GetProcessUseCase getProcessUseCase;
  
  @org.springframework.beans.factory.annotation.Autowired
  private GetControlImplementationsUseCase getControlImplementationsUseCase;
  
  @org.springframework.beans.factory.annotation.Autowired
  private ScopeRepository scopeRepository;
  
  @org.springframework.beans.factory.annotation.Autowired
  private UserAccessRightsProvider userAccessRightsProvider;
  
  @org.springframework.beans.factory.annotation.Autowired
  private org.veo.persistence.access.jpa.ScopeDataRepository scopeDataRepository;
  
  @org.springframework.beans.factory.annotation.Autowired
  private org.veo.persistence.access.jpa.AssetDataRepository assetDataRepository;

  @GetMapping(value = {"/reports", "/reports/"})
  @Operation(summary = "Get all available report types")
  @ApiResponse(responseCode = "200", description = "Reports metadata retrieved")
  public CompletableFuture<ResponseEntity<Map<String, Object>>> getReports() {
    // Standard reports available in Verinice
    Map<String, Object> reports = new HashMap<>();
    
    // Inventory of Assets
    Map<String, Object> inventoryOfAssets = new HashMap<>();
    Map<String, String> inventoryName = new HashMap<>();
    inventoryName.put("en", "Inventory of Assets");
    inventoryName.put("de", "Bestandsverzeichnis der Assets");
    inventoryOfAssets.put("name", inventoryName);
    
    Map<String, String> inventoryDesc = new HashMap<>();
    inventoryDesc.put("en", "Generates a comprehensive inventory of all assets in the selected scope.");
    inventoryDesc.put("de", "Erstellt ein umfassendes Bestandsverzeichnis aller Assets im ausgewählten Scope.");
    inventoryOfAssets.put("description", inventoryDesc);
    inventoryOfAssets.put("outputTypes", java.util.List.of("application/pdf"));
    inventoryOfAssets.put("multipleTargetsSupported", true);
    
    // Inventory of Assets targets SCOPES (not assets directly)
    // The report generates an inventory of assets within the selected scope(s)
    // IMPORTANT: modelType must be SINGULAR (scope, not scopes) - frontend converts to plural via VeoElementTypePlurals
    Map<String, Object> scopeTarget = new HashMap<>();
    scopeTarget.put("modelType", "scope");
    scopeTarget.put("subTypes", null);
    inventoryOfAssets.put("targetTypes", java.util.List.of(scopeTarget));
    reports.put("inventory-of-assets", inventoryOfAssets);
    // Note: "iso-inventory" is handled as an alias in the POST endpoint only
    // to avoid duplicate menu entries
    
    // Risk Assessment
    Map<String, Object> riskAssessment = new HashMap<>();
    Map<String, String> riskName = new HashMap<>();
    riskName.put("en", "Risk Assessment");
    riskName.put("de", "Risikobewertung");
    riskAssessment.put("name", riskName);
    
    Map<String, String> riskDesc = new HashMap<>();
    riskDesc.put("en", "Generates a detailed risk assessment report for the selected scopes, including all risks for assets and processes within those scopes.");
    riskDesc.put("de", "Erstellt einen detaillierten Risikobewertungsbericht für die ausgewählten Scopes, einschließlich aller Risiken für Assets und Prozesse innerhalb dieser Scopes.");
    riskAssessment.put("description", riskDesc);
    riskAssessment.put("outputTypes", java.util.List.of("application/pdf"));
    riskAssessment.put("multipleTargetsSupported", true);
    
    // Risk Assessment targets SCOPES only (not assets/processes directly)
    // The report generates risk assessment for risks within the selected scope(s)
    Map<String, Object> scopeTargetForRisk = new HashMap<>();
    scopeTargetForRisk.put("modelType", "scope");
    scopeTargetForRisk.put("subTypes", null);
    riskAssessment.put("targetTypes", java.util.List.of(scopeTargetForRisk));
    reports.put("risk-assessment", riskAssessment);
    
    // Statement of Applicability
    Map<String, Object> statementOfApplicability = new HashMap<>();
    Map<String, String> soaName = new HashMap<>();
    soaName.put("en", "Statement of Applicability");
    soaName.put("de", "Anwendbarkeitserklärung");
    statementOfApplicability.put("name", soaName);
    
    Map<String, String> soaDesc = new HashMap<>();
    soaDesc.put("en", "Generates a Statement of Applicability (SoA) report showing which controls are applicable and their implementation status.");
    soaDesc.put("de", "Erstellt eine Anwendbarkeitserklärung (SoA), die zeigt, welche Controls anwendbar sind und deren Umsetzungsstatus.");
    statementOfApplicability.put("description", soaDesc);
    statementOfApplicability.put("outputTypes", java.util.List.of("application/pdf"));
    statementOfApplicability.put("multipleTargetsSupported", false);
    
    Map<String, Object> scopeTarget2 = new HashMap<>();
    scopeTarget2.put("modelType", "scope");
    scopeTarget2.put("subTypes", null);
    statementOfApplicability.put("targetTypes", java.util.List.of(scopeTarget2));
    reports.put("statement-of-applicability", statementOfApplicability);

    return CompletableFuture.completedFuture(ResponseEntity.ok(reports));
  }

  @PostMapping("/reports/{type}")
  @Operation(summary = "Generate a report of the specified type")
  @ApiResponse(responseCode = "200", description = "Report generated successfully")
  @ApiResponse(responseCode = "404", description = "Report type not found")
  public CompletableFuture<ResponseEntity<byte[]>> generateReport(
      @PathVariable String type,
      @RequestBody Map<String, Object> requestBody) {
    // Validate report type exists - support both naming conventions
    Map<String, Object> availableReports = Map.of(
        "inventory-of-assets", Map.of("name", Map.of("en", "Inventory of Assets")),
        "iso-inventory", Map.of("name", Map.of("en", "Inventory of Assets")), // Verinice VEO alias
        "risk-assessment", Map.of("name", Map.of("en", "Risk Assessment")),
        "statement-of-applicability", Map.of("name", Map.of("en", "Statement of Applicability")));
    
    // Normalize report type (iso-inventory -> inventory-of-assets)
    String normalizedType = type;
    if ("iso-inventory".equals(type)) {
      normalizedType = "inventory-of-assets";
    }
    
    if (!availableReports.containsKey(type) && !availableReports.containsKey(normalizedType)) {
      return CompletableFuture.completedFuture(
          ResponseEntity.notFound().build());
    }

    // Extract request parameters
    String outputType = (String) requestBody.getOrDefault("outputType", "application/pdf");
    String language = (String) requestBody.getOrDefault("language", "en");
    @SuppressWarnings("unchecked")
    java.util.List<Map<String, Object>> targets = 
        (java.util.List<Map<String, Object>>) requestBody.getOrDefault("targets", java.util.List.of());
    String timeZone = (String) requestBody.getOrDefault("timeZone", "UTC");

    // Generate report based on normalized type
    if ("inventory-of-assets".equals(normalizedType)) {
      return generateInventoryOfAssetsReport(targets, language, outputType);
    } else if ("risk-assessment".equals(type)) {
      return generateRiskAssessmentReport(targets, language, outputType);
    } else if ("statement-of-applicability".equals(type)) {
      return generateStatementOfApplicabilityReport(targets, language, outputType);
    }
    
    // Placeholder for other report types
    String pdfContent = generatePlaceholderPDF(type);
    byte[] pdfBytes = pdfContent.getBytes(java.nio.charset.StandardCharsets.UTF_8);

    HttpHeaders headers = new HttpHeaders();
    headers.setContentType(MediaType.APPLICATION_PDF);
    headers.setContentDispositionFormData("attachment", type + "-report.pdf");
    headers.setContentLength(pdfBytes.length);

    return CompletableFuture.completedFuture(
        ResponseEntity.ok()
            .headers(headers)
            .body(pdfBytes));
  }

  private CompletableFuture<ResponseEntity<byte[]>> generateInventoryOfAssetsReport(
      List<Map<String, Object>> targets, String language, String outputType) {
    
    StringBuilder reportContent = new StringBuilder();
    // Professional header format matching Verinice VEO
    reportContent.append("# Inventory of Assets\n\n");
    reportContent.append("powered by SparksBM\n\n");  
    
    // Collect all assets from all scopes
    Set<Asset> allAssets = new java.util.HashSet<>();
    java.util.Map<String, Integer> memberTypeCounts = new java.util.HashMap<>();
    StringBuilder scopeInfo = new StringBuilder();
    String scopeName = "N/A"; // Store scope name for later use
    
    for (Map<String, Object> target : targets) {
      String scopeId = (String) target.get("id");
      if (scopeId == null) continue;
      
      try {
        UUID scopeUuid = UUID.fromString(scopeId);
        String domainId = (String) target.get("domainId");
        UUID domainUuid = domainId != null ? UUID.fromString(domainId) : null;
        
        // Fetch scope WITH members eagerly loaded using EntityGraph
        // This ensures members are loaded within the transaction
        Scope scope = null;
        org.veo.core.entity.Domain domain = null;
        
        // Use repository method that eagerly fetches members using @EntityGraph
        java.util.List<org.veo.persistence.entity.jpa.ScopeData> scopesWithMembers = 
            scopeDataRepository.findAllWithMembersByIdIn(java.util.List.of(scopeUuid));
        
        if (!scopesWithMembers.isEmpty()) {
          scope = scopesWithMembers.get(0);
          // Get domain from scope - access domains within transaction
          try {
            java.util.Set<org.veo.core.entity.Domain> scopeDomains = scope.getDomains();
            Hibernate.initialize(scopeDomains);
            if (domainUuid != null) {
              domain = scopeDomains.stream()
                  .filter(d -> d.getId().equals(domainUuid))
                  .findFirst()
                  .orElse(scopeDomains.stream().findFirst().orElse(null));
            } else {
              domain = scopeDomains.stream().findFirst().orElse(null);
            }
          } catch (Exception e) {
            // If domain access fails, continue without domain
            domain = null;
          }
        } else {
          // Fallback to use case if repository method doesn't work
          GetElementUseCase.OutputData<Scope> scopeOutput = useCaseInteractor.execute(
              getScopeUseCase,
              new GetElementUseCase.InputData(scopeUuid, domainUuid, false),
              output -> output
          ).join();
          scope = scopeOutput.element();
          domain = scopeOutput.domain();
        }
        
        if (scope != null) {
          // Format scope info consistently
          scopeName = scope.getDisplayName() != null ? scope.getDisplayName() : "N/A";
          scopeInfo.append("ISMS Scope: ").append(scopeName).append("\n");
          
          // Format creation date
          java.time.LocalDateTime now = java.time.LocalDateTime.now();
          java.time.format.DateTimeFormatter formatter = java.time.format.DateTimeFormatter.ofPattern("MMM dd, yyyy");
          scopeInfo.append("Creation date: ").append(now.format(formatter)).append("\n\n");
          
          // Get all members of this scope (assets, processes, etc.)
          // Members should be eagerly loaded by findAllWithMembersByIdIn
          Set<Element> members = scope.getMembers();
          
          // Force Hibernate to initialize the members collection immediately
          Hibernate.initialize(members);
          
          // Count member types and collect asset IDs
          java.util.List<UUID> assetIds = new java.util.ArrayList<>();
          for (Element member : members) {
            // Access basic properties to ensure member is loaded
            member.getDisplayName();
            member.getId();
            
            String memberType = member.getClass().getSimpleName().replace("Data", "");
            memberTypeCounts.put(memberType, memberTypeCounts.getOrDefault(memberType, 0) + 1);
            
            if (member instanceof Asset) {
              assetIds.add(member.getId());
            }
          }
          
          // Eagerly load assets with domainAssociations to avoid lazy loading errors
          if (!assetIds.isEmpty()) {
            java.util.List<org.veo.persistence.entity.jpa.AssetData> assetsWithDomains = 
                assetDataRepository.findAllWithDomainAssociationsByIdIn(assetIds);
            for (org.veo.persistence.entity.jpa.AssetData assetData : assetsWithDomains) {
              allAssets.add(assetData);
            }
          }
          
          // Don't show member type summary - match Verinice format
        }
      } catch (Exception e) {
        scopeInfo.append("Error loading scope ").append(scopeId).append(": ").append(e.getMessage()).append("\n");
      }
    }
    
    reportContent.append(scopeInfo);
    reportContent.append("---\n\n");
    
    // Debug logging
    System.out.println("[Report] Total assets found: " + allAssets.size());
    System.out.println("[Report] Report content length: " + reportContent.length());
    if (!allAssets.isEmpty()) {
      System.out.println("[Report] First asset: " + allAssets.iterator().next().getDisplayName());
    }
    
    if (allAssets.isEmpty()) {
      reportContent.append("# Main page\n\n");
      reportContent.append("No assets found in this scope.\n\n");
    } else {
      // Calculate total pages needed (estimate: ~15 lines per asset, 60 lines per page)
      int linesPerAsset = 15;
      int linesPerPage = 60;
      int totalLines = allAssets.size() * linesPerAsset + 20; // +20 for headers/tables
      int totalPages = Math.max(1, (totalLines + linesPerPage - 1) / linesPerPage);
      
      // Main page with scope info
      reportContent.append("# Main page\n\n");
      reportContent.append("ISMS Scope: ").append(scopeName).append("\n");
      reportContent.append("Creation date: ").append(java.time.LocalDateTime.now()
          .format(java.time.format.DateTimeFormatter.ofPattern("MMM dd, yyyy"))).append("\n");
      if (totalPages > 1) {
        reportContent.append("Page 1 of ").append(totalPages).append("\n\n");
      } else {
        reportContent.append("Page 1 of 1\n\n");
      }
      
      // Overview table header - match Verinice format exactly
      reportContent.append("# Overview\n\n");
      reportContent.append("|  Abbreviation | c | i | a | Name  |\n");
      reportContent.append("| --- | --- | --- | --- | --- |\n");
      
      // First pass: Build overview table with all assets
      // Collect asset data for both table and details
      java.util.List<java.util.Map<String, Object>> assetDataList = new java.util.ArrayList<>();
      
      for (Asset asset : allAssets) {
        String assetName = asset.getName() != null ? asset.getName() : "N/A";
        String abbreviation = asset.getAbbreviation() != null ? asset.getAbbreviation() : "N/A";
        
        // Get domain for asset metadata - domains are already eagerly loaded
        org.veo.core.entity.Domain assetDomain = null;
        try {
          java.util.Set<org.veo.core.entity.Domain> domains = asset.getDomains();
          if (domains != null && !domains.isEmpty()) {
            assetDomain = domains.iterator().next();
          }
        } catch (Exception e) {
          // If domains not accessible, continue without domain
        }
        
        String description = asset.getDescription() != null ? asset.getDescription() : "";
        String status = "NEW";
        String subType = "";
        
        // Get subType and status from domain association
        if (assetDomain != null) {
          try {
            status = asset.getStatus(assetDomain);
            subType = asset.getSubType(assetDomain);
          } catch (Exception e) {
            // Use defaults if not available
          }
        }
        
        // Try to extract CIA values from impact values (if available)
        String ciaConfidentiality = "";
        String ciaIntegrity = "";
        String ciaAvailability = "";
        
        if (assetDomain != null && asset instanceof org.veo.core.entity.RiskAffected) {
          try {
            org.veo.core.entity.RiskAffected<?, ?> riskAffected = (org.veo.core.entity.RiskAffected<?, ?>) asset;
            java.util.Map<org.veo.core.entity.risk.RiskDefinitionRef, org.veo.core.entity.risk.ImpactValues> impactValues = 
                riskAffected.getImpactValues(assetDomain);
            
            // Try to find CIA values from impact values
            // This is complex - for now, leave empty as Verinice example shows empty values
            // Future: Extract from risk definition categories
          } catch (Exception e) {
            // CIA values not available
          }
        }
        
        // Get last update date from asset
        java.time.LocalDateTime lastUpdate;
        if (asset.getUpdatedAt() != null) {
          lastUpdate = java.time.LocalDateTime.ofInstant(
            asset.getUpdatedAt(), 
            java.time.ZoneId.systemDefault()
          );
        } else {
          lastUpdate = java.time.LocalDateTime.now();
        }
        
        // Store asset data for later use
        java.util.Map<String, Object> assetData = new java.util.HashMap<>();
        assetData.put("name", assetName);
        assetData.put("abbreviation", abbreviation);
        assetData.put("description", description);
        assetData.put("status", status);
        assetData.put("subType", subType);
        assetData.put("ciaConfidentiality", ciaConfidentiality);
        assetData.put("ciaIntegrity", ciaIntegrity);
        assetData.put("ciaAvailability", ciaAvailability);
        assetData.put("lastUpdate", lastUpdate);
        assetDataList.add(assetData);
        
        // Add to overview table - match Verinice format
        reportContent.append("|  ").append(abbreviation).append(" | ").append(ciaConfidentiality)
            .append(" | ").append(ciaIntegrity).append(" | ").append(ciaAvailability)
            .append(" | ").append(assetName).append("  |\n");
      }
      
      // Assets section - add asset details after the overview table
      reportContent.append("\n# Assets\n\n");
      
      int index = 1;
      int currentPage = 1;
      int linesOnCurrentPage = 20; // Start after headers and overview table
      // linesPerPage is already declared above (line 363)
      
      for (java.util.Map<String, Object> assetData : assetDataList) {
        String assetName = (String) assetData.get("name");
        String abbreviation = (String) assetData.get("abbreviation");
        String description = (String) assetData.get("description");
        String status = (String) assetData.get("status");
        String subType = (String) assetData.get("subType");
        String ciaConfidentiality = (String) assetData.get("ciaConfidentiality");
        String ciaIntegrity = (String) assetData.get("ciaIntegrity");
        String ciaAvailability = (String) assetData.get("ciaAvailability");
        java.time.LocalDateTime lastUpdate = (java.time.LocalDateTime) assetData.get("lastUpdate");
        
        // Check if we need a new page
        linesOnCurrentPage += 15;
        if (linesOnCurrentPage > linesPerPage && totalPages > 1) {
          currentPage++;
          linesOnCurrentPage = 15;
          reportContent.append("\n# Main page\n\n");
          reportContent.append("ISMS Scope: ").append(scopeName).append("\n");
          reportContent.append("Creation date: ").append(java.time.LocalDateTime.now()
              .format(java.time.format.DateTimeFormatter.ofPattern("MMM dd, yyyy"))).append("\n");
          reportContent.append("Page ").append(currentPage).append(" of ").append(totalPages).append("\n\n");
        }
        
        // Asset details section - match Verinice format exactly
        reportContent.append("## ").append(assetName).append("\n\n");
        if (!description.isEmpty()) {
          reportContent.append("Description\n\n").append(description).append("\n\n");
        }
        reportContent.append("Type of asset\n\n");
        if (!subType.isEmpty()) {
          reportContent.append(subType).append("\n\n");
        } else {
          reportContent.append("\n");
        }
        reportContent.append("Number ").append(index++).append("\n\n");
        reportContent.append("Operating stage\n\n");
        if (!status.isEmpty() && !status.equals("NEW")) {
          reportContent.append(status).append("\n\n");
        } else {
          reportContent.append("\n");
        }
        reportContent.append("Confidentiality (C)\n\n");
        if (!ciaConfidentiality.isEmpty()) {
          reportContent.append(ciaConfidentiality).append("\n\n");
        } else {
          reportContent.append("\n");
        }
        reportContent.append("Integrity (I)\n\n");
        if (!ciaIntegrity.isEmpty()) {
          reportContent.append(ciaIntegrity).append("\n\n");
        } else {
          reportContent.append("\n");
        }
        reportContent.append("Availability (A)\n\n");
        if (!ciaAvailability.isEmpty()) {
          reportContent.append(ciaAvailability).append("\n\n");
        } else {
          reportContent.append("\n");
        }
        
        reportContent.append("Last update ").append(lastUpdate
            .format(java.time.format.DateTimeFormatter.ofPattern("MMM dd, yyyy, h:mm:ss a"))).append("\n\n");
        reportContent.append("---\n\n");
      }
    }
    
    // Generate PDF from content - use ASCII for PDF content streams
    String pdfContent = generatePDFFromText(reportContent.toString(), "Inventory of Assets");
    byte[] pdfBytes = pdfContent.getBytes(java.nio.charset.StandardCharsets.ISO_8859_1);
    
    HttpHeaders headers = new HttpHeaders();
    headers.setContentType(MediaType.APPLICATION_PDF);
    headers.setContentDispositionFormData("attachment", "inventory-of-assets-report.pdf");
    headers.setContentLength(pdfBytes.length);
    
    return CompletableFuture.completedFuture(
        ResponseEntity.ok().headers(headers).body(pdfBytes));
  }

  private CompletableFuture<ResponseEntity<byte[]>> generateRiskAssessmentReport(
      List<Map<String, Object>> targets, String language, String outputType) {
    
    StringBuilder reportContent = new StringBuilder();
    // Professional header format matching Verinice VEO
    reportContent.append("# Risk Assessment\n\n");
    reportContent.append("powered by SparksBM\n\n");
    
    // Collect all risk-affected elements and their risks
    // Risk Assessment only works with SCOPES - we get risks from scope and its members (assets/processes)
    java.util.List<RiskAssessmentEntry> riskEntries = new java.util.ArrayList<>();
    
    for (Map<String, Object> target : targets) {
      String scopeId = (String) target.get("id");
      String domainId = (String) target.get("domainId");
      if (scopeId == null) continue;
      
      try {
        UUID scopeUuid = UUID.fromString(scopeId);
        UUID domainUuid = domainId != null ? UUID.fromString(domainId) : null;
        
        // Fetch scope
        GetElementUseCase.OutputData<Scope> scopeOutput = useCaseInteractor.execute(
            getScopeUseCase,
            new GetElementUseCase.InputData(scopeUuid, domainUuid, true), // embedRisks = true
            o -> o
        ).join();
        
        Scope scope = scopeOutput.element();
        Domain domain = scopeOutput.domain();
        
        if (scope == null) {
          reportContent.append("Error: Scope not found for ").append(scopeId).append("\n");
          continue;
        }
        
        // Use domain from scope if not provided
        if (domain == null && !scope.getDomains().isEmpty()) {
          domain = scope.getDomains().iterator().next();
        }
        
        // Get risks directly on the scope
        Set<? extends AbstractRisk<?, ?>> scopeRisks = scope.getRisks();
        for (AbstractRisk<?, ?> risk : scopeRisks) {
          RiskAssessmentEntry entry = new RiskAssessmentEntry();
          entry.elementType = "scope";
          entry.elementName = scope.getDisplayName();
          entry.elementDesignator = scope.getDesignator();
          entry.scenario = risk.getScenario();
          entry.mitigation = risk.getMitigation();
          entry.riskOwner = risk.getRiskOwner();
          entry.risk = risk;
          entry.domain = domain;
          riskEntries.add(entry);
        }
        
        // Get risks from scope members (assets and processes)
        // Use same eager loading approach as Inventory report
        Set<Element> members = scope.getMembers();
        Hibernate.initialize(members);
        
        int memberCount = 0;
        java.util.List<UUID> memberIds = new java.util.ArrayList<>();
        
        for (Element member : members) {
          memberCount++;
          if (member != null) {
            memberIds.add(member.getId());
            try {
              member.getDisplayName(); // Force initialization
              if (member instanceof RiskAffected) {
                RiskAffected<?, ?> riskAffected = (RiskAffected<?, ?>) member;
                Set<? extends AbstractRisk<?, ?>> memberRisks = riskAffected.getRisks();
                Hibernate.initialize(memberRisks);
            
                for (AbstractRisk<?, ?> risk : memberRisks) {
                  RiskAssessmentEntry entry = new RiskAssessmentEntry();
                  if (member instanceof Asset) {
                    entry.elementType = "asset";
                  } else if (member instanceof Process) {
                    entry.elementType = "process";
                  } else {
                    entry.elementType = member.getModelInterface().getSimpleName().toLowerCase();
                  }
                  entry.elementName = member.getDisplayName();
                  entry.elementDesignator = member.getDesignator();
                  entry.scenario = risk.getScenario();
                  entry.mitigation = risk.getMitigation();
                  entry.riskOwner = risk.getRiskOwner();
                  entry.risk = risk;
                  entry.domain = domain;
                  riskEntries.add(entry);
                }
              }
            } catch (org.hibernate.LazyInitializationException e) {
              // Try to reload member with risks
              try {
                if (member instanceof Asset) {
                  org.veo.persistence.entity.jpa.AssetData assetData = 
                      assetDataRepository.findById(member.getId()).orElse(null);
                  if (assetData != null && assetData instanceof RiskAffected) {
                    RiskAffected<?, ?> riskAffected = (RiskAffected<?, ?>) assetData;
                    Set<? extends AbstractRisk<?, ?>> memberRisks = riskAffected.getRisks();
                    for (AbstractRisk<?, ?> risk : memberRisks) {
                      RiskAssessmentEntry entry = new RiskAssessmentEntry();
                      entry.elementType = "asset";
                      entry.elementName = assetData.getDisplayName();
                      entry.elementDesignator = assetData.getDesignator();
                      entry.scenario = risk.getScenario();
                      entry.mitigation = risk.getMitigation();
                      entry.riskOwner = risk.getRiskOwner();
                      entry.risk = risk;
                      entry.domain = domain;
                      riskEntries.add(entry);
                    }
                  }
                }
              } catch (Exception ex) {
                // Skip this member
              }
            } catch (Exception e) {
              // Skip this member
            }
          }
        }
        
        String scopeName = scope.getDisplayName() != null ? scope.getDisplayName() : "N/A";
        String scopeDescription = scope.getDescription() != null ? scope.getDescription() : "";
        String scopeStatus = domain != null ? scope.getStatus(domain) : "NEW";
        
        // Format organisation/scope info - match Verinice format
        reportContent.append("Organisation: ").append(scopeName).append("\n");
        java.time.LocalDateTime now = java.time.LocalDateTime.now();
        java.time.format.DateTimeFormatter formatter = java.time.format.DateTimeFormatter.ofPattern("MMM dd, yyyy");
        reportContent.append("Creation date: ").append(now.format(formatter)).append("\n\n");
        reportContent.append("---\n\n");
      } catch (Exception e) {
        reportContent.append("Error loading scope ").append(scopeId)
            .append(": ").append(e.getMessage()).append("\n");
      }
    }
    
    // Main page - match Verinice format
    reportContent.append("# Main page\n\n");
    if (!riskEntries.isEmpty()) {
      String scopeName = riskEntries.get(0).elementName;
      reportContent.append("The ISMS Scope is not a member of any organization.\n\n");
      reportContent.append("ISMS Scope\n");
      reportContent.append("- Name: ").append(scopeName).append("\n");
      if (!riskEntries.isEmpty() && riskEntries.get(0).domain != null) {
        reportContent.append("- Description: ").append(riskEntries.get(0).domain.getName()).append("\n");
      }
      reportContent.append("- Status: New\n\n");
      reportContent.append("Organisation: ").append(scopeName).append("\n");
      java.time.LocalDateTime now = java.time.LocalDateTime.now();
      java.time.format.DateTimeFormatter formatter = java.time.format.DateTimeFormatter.ofPattern("MMM dd, yyyy");
      reportContent.append("Creation date: ").append(now.format(formatter)).append("\n\n");
      reportContent.append("---\n\n");
    }
    
    if (riskEntries.isEmpty()) {
      reportContent.append("No risks found in the selected scope(s).\n\n");
    } else {
      // Generate detailed risk assessment
      reportContent.append("DETAILED RISK ASSESSMENT\n");
      reportContent.append("========================\n\n");
      
      String currentElement = null;
      int riskIndex = 1;
      
      for (RiskAssessmentEntry entry : riskEntries) {
      // New element section
      if (!entry.elementDesignator.equals(currentElement)) {
        if (currentElement != null) {
          reportContent.append("\n");
        }
        currentElement = entry.elementDesignator;
        reportContent.append("ELEMENT: ").append(entry.elementDesignator).append(" - ")
            .append(entry.elementName).append("\n");
        reportContent.append("Type: ").append(entry.elementType.toUpperCase()).append("\n");
        if (entry.domain != null) {
          reportContent.append("Domain: ").append(entry.domain.getName()).append("\n");
        }
        reportContent.append("─────────────────────────────────────────\n\n");
      }
      
      // Risk details
      reportContent.append("Risk #").append(riskIndex++).append("\n");
      reportContent.append("───────\n");
      
      // Scenario
      Scenario scenario = entry.scenario;
      if (scenario != null) {
        reportContent.append("Scenario: ").append(scenario.getDisplayName()).append("\n");
        reportContent.append("  Designator: ").append(scenario.getDesignator()).append("\n");
        if (scenario.getDescription() != null) {
          reportContent.append("  Description: ").append(scenario.getDescription()).append("\n");
        }
      }
      
      // Risk Owner
      Person riskOwner = entry.riskOwner;
      if (riskOwner != null) {
        reportContent.append("Risk Owner: ").append(riskOwner.getDisplayName()).append("\n");
      }
      
      // Mitigation
      Control mitigation = entry.mitigation;
      if (mitigation != null) {
        reportContent.append("Mitigation: ").append(mitigation.getDisplayName()).append("\n");
        reportContent.append("  Designator: ").append(mitigation.getDesignator()).append("\n");
      }
      
      // Risk Values (if domain and risk definitions available)
      if (entry.domain != null) {
        Domain d = entry.domain;
        Set<RiskDefinitionRef> riskDefs = entry.risk.getRiskDefinitions(d);
        
        for (RiskDefinitionRef riskDefRef : riskDefs) {
          reportContent.append("\nRisk Definition: ").append(riskDefRef.getIdRef()).append("\n");
          
          try {
            // Get probability
            Probability probability = entry.risk.getProbabilityProvider(riskDefRef, d).getProbability();
            if (probability != null && probability.getEffectiveProbability() != null) {
              reportContent.append("  Probability: ").append(probability.getEffectiveProbability().getIdRef()).append("\n");
            }
            
            // Get impact values
            java.util.List<Impact> impacts = entry.risk.getImpactProvider(riskDefRef, d).getCategorizedImpacts();
            if (impacts != null && !impacts.isEmpty()) {
              reportContent.append("  Impact Values:\n");
              for (Impact impact : impacts) {
                String category = impact.getCategory() != null ? impact.getCategory().getIdRef() : "N/A";
                String impactValue = impact.getEffectiveImpact() != null ? 
                    impact.getEffectiveImpact().getIdRef().toString() : "N/A";
                reportContent.append("    - ").append(category).append(": ").append(impactValue).append("\n");
              }
            }
            
            // Get categorized risks (with treatments and residual risks)
            java.util.List<DeterminedRisk> determinedRisks = 
                entry.risk.getRiskProvider(riskDefRef, d).getCategorizedRisks();
            if (determinedRisks != null && !determinedRisks.isEmpty()) {
              reportContent.append("  Risk Values:\n");
              for (DeterminedRisk detRisk : determinedRisks) {
                String category = detRisk.getCategory() != null ? detRisk.getCategory().getIdRef() : "N/A";
                reportContent.append("    Category ").append(category).append(":\n");
                
                if (detRisk.getInherentRisk() != null) {
                  reportContent.append("      Inherent Risk: ").append(detRisk.getInherentRisk().getIdRef()).append("\n");
                }
                
                if (detRisk.getResidualRisk() != null) {
                  reportContent.append("      Residual Risk: ").append(detRisk.getResidualRisk().getIdRef()).append("\n");
                }
                
                if (detRisk.getRiskTreatments() != null && !detRisk.getRiskTreatments().isEmpty()) {
                  reportContent.append("      Treatments: ");
                  reportContent.append(String.join(", ", detRisk.getRiskTreatments().stream()
                      .map(Enum::name).collect(Collectors.toList()))).append("\n");
                }
                
                if (detRisk.getRiskTreatmentExplanation() != null && !detRisk.getRiskTreatmentExplanation().isEmpty()) {
                  reportContent.append("      Treatment Explanation: ").append(detRisk.getRiskTreatmentExplanation()).append("\n");
                }
                
                if (detRisk.getResidualRiskExplanation() != null && !detRisk.getResidualRiskExplanation().isEmpty()) {
                  reportContent.append("      Residual Risk Explanation: ").append(detRisk.getResidualRiskExplanation()).append("\n");
                }
              }
            }
          } catch (Exception e) {
            reportContent.append("  (Risk values not available: ").append(e.getMessage()).append(")\n");
          }
        }
      }
      
      reportContent.append("\n");
      }
    }
    
    // Generate PDF from content
    String pdfContent = generatePDFFromText(reportContent.toString(), "Risk Assessment");
    byte[] pdfBytes = pdfContent.getBytes(java.nio.charset.StandardCharsets.UTF_8);
    
    HttpHeaders headers = new HttpHeaders();
    headers.setContentType(MediaType.APPLICATION_PDF);
    headers.setContentDispositionFormData("attachment", "risk-assessment-report.pdf");
    headers.setContentLength(pdfBytes.length);
    
    return CompletableFuture.completedFuture(
        ResponseEntity.ok().headers(headers).body(pdfBytes));
  }
  
  private CompletableFuture<ResponseEntity<byte[]>> generateStatementOfApplicabilityReport(
      List<Map<String, Object>> targets, String language, String outputType) {
    
    StringBuilder reportContent = new StringBuilder();
    // Professional header format matching Verinice VEO
    reportContent.append("# Statement of Applicability\n\n");
    reportContent.append("powered by SparksBM\n\n");
    
    // Process each scope target
    for (Map<String, Object> target : targets) {
      String scopeId = (String) target.get("id");
      String domainId = (String) target.get("domainId");
      if (scopeId == null || domainId == null) continue;
      
      try {
        UUID scopeUuid = UUID.fromString(scopeId);
        UUID domainUuid = UUID.fromString(domainId);
        
        // Fetch scope
        GetElementUseCase.OutputData<Scope> scopeOutput = useCaseInteractor.execute(
            getScopeUseCase,
            new GetElementUseCase.InputData(scopeUuid, domainUuid, false),
            output -> output
        ).join();
        
        Scope scope = scopeOutput.element();
        Domain domain = scopeOutput.domain();
        
        if (scope == null || domain == null) {
          reportContent.append("Error: Scope or domain not found for ").append(scopeId).append("\n\n");
          continue;
        }
        
        // Format scope info - match Verinice format
        String scopeName = scope.getDisplayName() != null ? scope.getDisplayName() : "N/A";
        reportContent.append("ISMS Scope: ").append(scopeName).append("\n");
        java.time.LocalDateTime now = java.time.LocalDateTime.now();
        java.time.format.DateTimeFormatter formatter = java.time.format.DateTimeFormatter.ofPattern("MMM dd, yyyy");
        reportContent.append("Creation date: ").append(now.format(formatter)).append("\n\n");
        reportContent.append("---\n\n");
        
        // Main page - match Verinice format
        reportContent.append("# Main page\n\n");
        reportContent.append("ISMS Scope: ").append(scopeName).append("\n");
        reportContent.append("Creation date: ").append(now.format(formatter)).append("\n");
        reportContent.append("Page 1 of 1\n\n");
        
        // Get control implementations for this scope
        GetControlImplementationsUseCase.InputData ciInput = 
            new GetControlImplementationsUseCase.InputData(
                null, // controlId - null to get all
                domainUuid,
                TypedId.from(scopeUuid, Scope.class),
                null, // purpose filter - null for all
                new PagingConfiguration<>(1000, 0, "name", PagingConfiguration.SortOrder.ASCENDING) // Get all controls
            );
        
        GetControlImplementationsUseCase.OutputData ciOutput = useCaseInteractor.execute(
            getControlImplementationsUseCase,
            ciInput,
            output -> output
        ).join();
        
        java.util.List<ControlImplementation> controlImplementations = 
            new java.util.ArrayList<>(ciOutput.page().getResultPage());
        
        // Controls table - match Verinice format exactly
        reportContent.append("# Controls\n\n");
        reportContent.append("|  Abbr. | Name | App. | Implementation status | Reason for applicability or exclusion  |\n");
        reportContent.append("| --- | --- | --- | --- | --- |\n");
        
        if (controlImplementations.isEmpty()) {
          // Empty table row
          reportContent.append("|  |  |  |  |  |\n");
        } else {
          for (ControlImplementation ci : controlImplementations) {
            Control control = ci.getControl();
            String abbr = control.getAbbreviation() != null ? control.getAbbreviation() : "";
            String name = control.getDisplayName() != null ? control.getDisplayName() : "";
            String app = ""; // Applicability - not directly available, leave empty
            String implStatus = "Not specified";
            String reason = "";
            
            // Get requirement implementations for this control implementation
            Set<ReqImplRef> reqImplRefs = ci.getRequirementImplementations();
            if (reqImplRefs != null && !reqImplRefs.isEmpty()) {
              RiskAffected<?, ?> owner = ci.getOwner();
              Set<RequirementImplementation> ownerReqImpls = owner.getRequirementImplementations();
              
              // Match ReqImplRefs to actual RequirementImplementations
              for (ReqImplRef ref : reqImplRefs) {
                try {
                  UUID refId = ref.getUUID();
                  RequirementImplementation ri = ownerReqImpls.stream()
                      .filter(r -> r.getId().equals(refId))
                      .findFirst()
                      .orElse(null);
                  
                  if (ri != null) {
                    ImplementationStatus status = ri.getStatus();
                    implStatus = status != null ? status.name() : "NOT_SPECIFIED";
                    
                    if (ri.getImplementationStatement() != null && !ri.getImplementationStatement().isEmpty()) {
                      reason = ri.getImplementationStatement();
                    }
                    break; // Use first requirement implementation
                  }
                } catch (Exception e) {
                  // Skip invalid ref
                }
              }
            }
            
            // Add table row - match Verinice format
            reportContent.append("|  ").append(abbr).append(" | ").append(name)
                .append(" | ").append(app).append(" | ").append(implStatus)
                .append(" | ").append(reason).append("  |\n");
          }
        }
        
        // Footer
        reportContent.append("\nISMS Scope: ").append(scopeName).append("\n");
        reportContent.append("Creation date: ").append(now.format(formatter)).append("\n");
        
      } catch (Exception e) {
        reportContent.append("Error loading scope ").append(scopeId)
            .append(": ").append(e.getMessage()).append("\n\n");
      }
    }
    
    // Generate PDF from content
    String pdfContent = generatePDFFromText(reportContent.toString(), "Statement of Applicability");
    byte[] pdfBytes = pdfContent.getBytes(java.nio.charset.StandardCharsets.UTF_8);
    
    HttpHeaders headers = new HttpHeaders();
    headers.setContentType(MediaType.APPLICATION_PDF);
    headers.setContentDispositionFormData("attachment", "statement-of-applicability-report.pdf");
    headers.setContentLength(pdfBytes.length);
    
    return CompletableFuture.completedFuture(
        ResponseEntity.ok().headers(headers).body(pdfBytes));
  }
  
  /**
   * Escape text for PDF content streams
   * PDF text strings must escape: \ ( ) and handle special characters
   */
  private String escapePDFText(String text) {
    if (text == null) {
      return "";
    }
    
    // Remove carriage returns and newlines (we handle line breaks separately)
    String cleaned = text.replace("\r", "").replace("\n", "");
    
    // Escape special PDF characters in correct order
    // Backslash must be escaped first
    StringBuilder escaped = new StringBuilder();
    for (int i = 0; i < cleaned.length(); i++) {
      char c = cleaned.charAt(i);
      switch (c) {
        case '\\':
          escaped.append("\\\\");
          break;
        case '(':
          escaped.append("\\(");
          break;
        case ')':
          escaped.append("\\)");
          break;
        case '\r':
        case '\n':
          // Already removed above, but handle just in case
          break;
        default:
          // For ASCII printable characters (32-126), use as-is
          // For non-ASCII characters, convert to octal escape sequence
          if (c >= 32 && c <= 126) {
            escaped.append(c);
          } else if (c < 256) {
            // For Latin-1 characters, use octal escape
            escaped.append("\\").append(String.format("%03o", (int) c));
          } else {
            // For Unicode characters, use UTF-16BE encoding (simplified)
            // For now, replace with question mark to avoid corruption
            escaped.append("?");
          }
          break;
      }
    }
    
    return escaped.toString();
  }
  
  /**
   * Add page header with title and page number - exact positioning
   */
  private void addPageHeaderExact(StringBuilder stream, int pageNum, int totalPages, int marginLeft, int yPos, int fontSizeTitle, int fontSizeBody) {
    // Title
    stream.append("/F1 ").append(fontSizeTitle).append(" Tf\n");
    stream.append("1 0 0 1 ").append(marginLeft).append(" ").append(yPos).append(" Tm\n");
    stream.append("(Inventory of Assets) Tj\n");
    
    // Subtitle
    stream.append("/F1 ").append(fontSizeBody - 1).append(" Tf\n");
    stream.append("1 0 0 1 ").append(marginLeft).append(" ").append(yPos - 14).append(" Tm\n");
    stream.append("(powered by SparksBM) Tj\n");
    
    stream.append("/F1 ").append(fontSizeBody).append(" Tf\n");
  }
  
  /**
   * Add page footer with page number - exact positioning matching reference
   */
  private void addPageFooterExact(StringBuilder stream, int pageNum, int totalPages, int pageWidth, int fontSize) {
    stream.append("ET\n");
    stream.append("BT\n");
    stream.append("/F1 ").append(fontSize).append(" Tf\n");
    String footerText = "Page " + pageNum + " of " + totalPages;
    String escaped = escapePDFText(footerText);
    // Position at bottom right, 1 inch from edges
    int footerX = pageWidth - 72 - 60; // Right margin - text width estimate
    int footerY = 50; // Bottom margin
    stream.append("1 0 0 1 ").append(footerX).append(" ").append(footerY).append(" Tm\n");
    stream.append("(").append(escaped).append(") Tj\n");
    stream.append("/F1 10 Tf\n");
  }
  
  // Helper class for risk assessment entries
  private static class RiskAssessmentEntry {
    String elementType;
    String elementName;
    String elementDesignator;
    Scenario scenario;
    Control mitigation;
    Person riskOwner;
    AbstractRisk<?, ?> risk;
    Domain domain;
  }

  private String generatePDFFromText(String text, String title) {
    // Parse text structure and build formatted PDF content streams matching reference exactly
    String[] lines = text.split("\n");
    
    // Exact measurements from reference images
    int pageWidth = 612;  // 8.5 inches at 72 DPI
    int pageHeight = 792; // 11 inches at 72 DPI
    int marginLeft = 72;   // 1 inch left margin
    int marginRight = 540; // 1 inch right margin (612 - 72)
    int marginTop = 720;   // Start 1 inch from top (792 - 72)
    int marginBottom = 72; // 1 inch bottom margin
    
    // Font sizes matching reference exactly
    int fontSizeTitle = 16;      // Main title
    int fontSizeHeading = 12;    // Section headings
    int fontSizeSubHeading = 11; // Sub-headings
    int fontSizeBody = 10;      // Body text
    int fontSizeTable = 9;       // Table text
    int fontSizeFooter = 9;      // Footer text
    
    // Line spacing matching reference
    int lineHeightBody = 12;     // Body text line height
    int lineHeightHeading = 16; // Heading line height
    int lineHeightTable = 11;    // Table row height
    int spacingAfterHeading = 8; // Space after headings
    int spacingAfterSection = 6; // Space after sections
    
    // Build content streams for each page
    java.util.List<String> pageStreams = new java.util.ArrayList<>();
    StringBuilder currentStream = new StringBuilder();
    currentStream.append("BT\n");
    
    int yPos = marginTop;
    int currentPage = 0;
    int totalPages = 1;
    
    // Calculate total pages
    int contentHeight = 0;
    for (String line : lines) {
      String trimmed = line.trim();
      if (trimmed.isEmpty()) {
        contentHeight += lineHeightBody / 2;
      } else if (trimmed.startsWith("# ")) {
        contentHeight += lineHeightHeading + spacingAfterHeading;
      } else if (trimmed.startsWith("## ")) {
        contentHeight += lineHeightHeading + spacingAfterHeading;
      } else if (trimmed.startsWith("|") && trimmed.contains("|")) {
        contentHeight += lineHeightTable;
      } else {
        contentHeight += lineHeightBody;
      }
    }
    totalPages = Math.max(1, (contentHeight + 100) / (marginTop - marginBottom));
    
    // Render content with exact formatting
    boolean inTable = false;
    int tableStartX = marginLeft;
    int[] tableColumnWidths = {100, 30, 30, 30, 300}; // Abbreviation, c, i, a, Name
    
    for (String line : lines) {
      // Check if we need a new page
      if (yPos < marginBottom + 50 && currentPage < totalPages - 1) {
        // Add footer
        addPageFooterExact(currentStream, currentPage + 1, totalPages, pageWidth, fontSizeFooter);
        currentStream.append("ET\n");
        pageStreams.add(currentStream.toString());
        currentPage++;
        yPos = marginTop;
        currentStream = new StringBuilder();
        currentStream.append("BT\n");
        // Add page header
        addPageHeaderExact(currentStream, currentPage + 1, totalPages, marginLeft, yPos, fontSizeTitle, fontSizeBody);
        yPos -= 50;
      }
      
      String trimmedLine = line.trim();
      
      // Handle different line types with exact formatting
      if (trimmedLine.isEmpty()) {
        yPos -= lineHeightBody / 2;
      } else if (trimmedLine.startsWith("# ")) {
        // Main heading (H1) - exact size and spacing
        String headingText = trimmedLine.substring(2).trim();
        String escaped = escapePDFText(headingText);
        currentStream.append("/F1 ").append(fontSizeHeading).append(" Tf\n");
        currentStream.append("1 0 0 1 ").append(marginLeft).append(" ").append(yPos).append(" Tm\n");
        currentStream.append("(").append(escaped).append(") Tj\n");
        yPos -= (lineHeightHeading + spacingAfterHeading);
        currentStream.append("/F1 ").append(fontSizeBody).append(" Tf\n");
      } else if (trimmedLine.startsWith("## ")) {
        // Subheading (H2) - exact size and spacing
        String headingText = trimmedLine.substring(3).trim();
        String escaped = escapePDFText(headingText);
        currentStream.append("/F1 ").append(fontSizeSubHeading).append(" Tf\n");
        currentStream.append("1 0 0 1 ").append(marginLeft).append(" ").append(yPos).append(" Tm\n");
        currentStream.append("(").append(escaped).append(") Tj\n");
        yPos -= (lineHeightHeading + spacingAfterHeading);
        currentStream.append("/F1 ").append(fontSizeBody).append(" Tf\n");
      } else if (trimmedLine.startsWith("|") && trimmedLine.contains("|")) {
        // Table row - exact column alignment
        String[] cells = trimmedLine.split("\\|", -1);
        int xPos = tableStartX;
        
        for (int i = 0; i < Math.min(cells.length, tableColumnWidths.length); i++) {
          String cellText = cells[i].trim();
          if (i == 0 && cellText.isEmpty()) continue; // Skip first empty cell
          
          // Check if it's a separator row
          if (cellText.equals("---") || cellText.matches("^-+$")) {
            // Draw table separator line
            currentStream.append("ET\n");
            currentStream.append(xPos).append(" ").append(yPos - 2).append(" m\n");
            currentStream.append(xPos + tableColumnWidths[i]).append(" ").append(yPos - 2).append(" l\n");
            currentStream.append("S\n");
            currentStream.append("BT\n");
            xPos += tableColumnWidths[i] + 10;
            continue;
          }
          
          if (!cellText.isEmpty()) {
            String escaped = escapePDFText(cellText);
            currentStream.append("/F1 ").append(fontSizeTable).append(" Tf\n");
            currentStream.append("1 0 0 1 ").append(xPos).append(" ").append(yPos).append(" Tm\n");
            currentStream.append("(").append(escaped).append(") Tj\n");
          }
          xPos += tableColumnWidths[i] + 10; // Column width + spacing
        }
        currentStream.append("/F1 ").append(fontSizeBody).append(" Tf\n");
        yPos -= lineHeightTable;
        inTable = true;
      } else if (trimmedLine.startsWith("---")) {
        // Horizontal rule - exact positioning
        currentStream.append("ET\n");
        currentStream.append(marginLeft).append(" ").append(yPos - 3).append(" m\n");
        currentStream.append(marginRight).append(" ").append(yPos - 3).append(" l\n");
        currentStream.append("0.5 w S\n"); // 0.5pt line width
        currentStream.append("BT\n");
        yPos -= 10;
        inTable = false;
      } else {
        // Regular text line - exact formatting
        // Check if it's a label-value pair (two-column layout)
        if (trimmedLine.contains(":") && !trimmedLine.startsWith("ISMS Scope") && !trimmedLine.startsWith("Creation date") && !trimmedLine.startsWith("Page")) {
          // Two-column layout: label on left, value on right
          int colonPos = trimmedLine.indexOf(":");
          if (colonPos > 0) {
            String label = trimmedLine.substring(0, colonPos + 1).trim();
            String value = trimmedLine.substring(colonPos + 1).trim();
            
            // Label on left
            String escapedLabel = escapePDFText(label);
            currentStream.append("/F1 ").append(fontSizeBody).append(" Tf\n");
            currentStream.append("1 0 0 1 ").append(marginLeft).append(" ").append(yPos).append(" Tm\n");
            currentStream.append("(").append(escapedLabel).append(") Tj\n");
            
            // Value on right (if not empty)
            if (!value.isEmpty()) {
              String escapedValue = escapePDFText(value);
              int valueX = marginLeft + 200; // Fixed position for values
              currentStream.append("1 0 0 1 ").append(valueX).append(" ").append(yPos).append(" Tm\n");
              currentStream.append("(").append(escapedValue).append(") Tj\n");
            }
          } else {
            // Regular line
            String escaped = escapePDFText(trimmedLine);
            currentStream.append("/F1 ").append(fontSizeBody).append(" Tf\n");
            currentStream.append("1 0 0 1 ").append(marginLeft).append(" ").append(yPos).append(" Tm\n");
            currentStream.append("(").append(escaped).append(") Tj\n");
          }
        } else {
          // Regular line
          String escaped = escapePDFText(trimmedLine);
          currentStream.append("/F1 ").append(fontSizeBody).append(" Tf\n");
          currentStream.append("1 0 0 1 ").append(marginLeft).append(" ").append(yPos).append(" Tm\n");
          currentStream.append("(").append(escaped).append(") Tj\n");
        }
        yPos -= lineHeightBody;
        inTable = false;
      }
    }
    
    // Add footer to last page
    addPageFooterExact(currentStream, currentPage + 1, totalPages, pageWidth, fontSizeFooter);
    currentStream.append("ET\n");
    pageStreams.add(currentStream.toString());
    
    // Build PDF with multiple pages
    StringBuilder pdf = new StringBuilder();
    pdf.append("%PDF-1.4\n");
    
    // Object 1: Catalog
    int obj1Pos = pdf.length();
    pdf.append("1 0 obj\n");
    pdf.append("<< /Type /Catalog /Pages 2 0 R >>\n");
    pdf.append("endobj\n");
    
    // Object 2: Pages (with all page kids)
    int obj2Pos = pdf.length();
    pdf.append("2 0 obj\n");
    pdf.append("<< /Type /Pages /Kids [");
    for (int i = 0; i < totalPages; i++) {
      pdf.append((3 + i * 2)).append(" 0 R");
      if (i < totalPages - 1) pdf.append(" ");
    }
    pdf.append("] /Count ").append(totalPages).append(" >>\n");
    pdf.append("endobj\n");
    
    // Page objects and content streams
    java.util.List<Integer> pageObjPositions = new java.util.ArrayList<>();
    java.util.List<Integer> streamObjPositions = new java.util.ArrayList<>();
    
    for (int i = 0; i < totalPages; i++) {
      // Page object
      int pageObjNum = 3 + i * 2;
      int streamObjNum = 4 + i * 2;
      int pageObjPos = pdf.length();
      pageObjPositions.add(pageObjPos);
      
      pdf.append(pageObjNum).append(" 0 obj\n");
      pdf.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents ")
          .append(streamObjNum).append(" 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Courier >> >> >> >>\n");
      pdf.append("endobj\n");
      
      // Content stream object
      String streamContent = pageStreams.get(i);
      int streamLength = streamContent.length();
      int streamObjPos = pdf.length();
      streamObjPositions.add(streamObjPos);
      
      pdf.append(streamObjNum).append(" 0 obj\n");
      pdf.append("<< /Length ").append(streamLength).append(" >>\n");
      pdf.append("stream\n");
      pdf.append(streamContent);
      pdf.append("endstream\n");
      pdf.append("endobj\n");
    }
    
    // Xref table
    int xrefPos = pdf.length();
    int totalObjects = 2 + totalPages * 2; // Catalog + Pages + (Page + Stream) * pages
    pdf.append("xref\n");
    pdf.append("0 ").append(totalObjects + 1).append("\n");
    pdf.append(String.format("%010d 65535 f \n", 0));
    pdf.append(String.format("%010d %05d n \n", obj1Pos, 0));
    pdf.append(String.format("%010d %05d n \n", obj2Pos, 0));
    
    for (int i = 0; i < totalPages; i++) {
      pdf.append(String.format("%010d %05d n \n", pageObjPositions.get(i), 0));
      pdf.append(String.format("%010d %05d n \n", streamObjPositions.get(i), 0));
    }
    
    // Trailer
    pdf.append("trailer\n");
    pdf.append("<< /Size ").append(totalObjects + 1).append(" /Root 1 0 R >>\n");
    pdf.append("startxref\n");
    pdf.append(xrefPos).append("\n");
    pdf.append("%%EOF");
    
    return pdf.toString();
  }

  private String generatePlaceholderPDF(String type) {
    return "%PDF-1.4\n" +
        "1 0 obj\n" +
        "<< /Type /Catalog /Pages 2 0 R >>\n" +
        "endobj\n" +
        "2 0 obj\n" +
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n" +
        "endobj\n" +
        "3 0 obj\n" +
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\n" +
        "endobj\n" +
        "4 0 obj\n" +
        "<< /Length 100 >>\n" +
        "stream\n" +
        "BT\n" +
        "/F1 12 Tf\n" +
        "100 700 Td\n" +
        "(" + type + " Report - Generation in progress) Tj\n" +
        "ET\n" +
        "endstream\n" +
        "endobj\n" +
        "xref\n" +
        "0 5\n" +
        "0000000000 65535 f \n" +
        "0000000009 00000 n \n" +
        "0000000058 00000 n \n" +
        "0000000115 00000 n \n" +
        "0000000306 00000 n \n" +
        "trailer\n" +
        "<< /Size 5 /Root 1 0 R >>\n" +
        "startxref\n" +
        "450\n" +
        "%%EOF";
  }
}
