<?xml version="1.0" encoding="UTF-8"?>
<!--
  cda-default.xsl - Default HL7 CDA R2 rendering stylesheet for cda2pdf.

  Copyright (C) 2026 Mint Medical PLLC
  SPDX-License-Identifier: AGPL-3.0-or-later

  This is an ORIGINAL, CLEAN-ROOM implementation written against the published
  HL7 Clinical Document Architecture Release 2 (CDA R2) specification and the
  CDA NarrativeBlock schema. It is not derived from, and contains no code from,
  any vendor-supplied CDA stylesheet.

  It renders the human-readable portion of a CDA document:
    - CDA header (patient demographics, document metadata, author, custodian,
      encompassing encounter)
    - Each structuredBody section's <title> and <text> NarrativeBlock

  Per CDA R2 section 1.2.1, the <text> NarrativeBlock is the attested,
  human-readable content of the document. This stylesheet reproduces it
  verbatim without summarization.
-->
<xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:cda="urn:hl7-org:v3"
                xmlns:sdtc="urn:hl7-org:sdtc"
                exclude-result-prefixes="cda sdtc">

  <xsl:output method="html" encoding="UTF-8" indent="no"
              doctype-public="-//W3C//DTD HTML 4.01//EN"/>

  <xsl:strip-space elements="*"/>
  <xsl:preserve-space elements="cda:text cda:paragraph cda:content cda:td cda:th cda:title"/>

  <!-- ==================================================================== -->
  <!-- Root                                                                 -->
  <!-- ==================================================================== -->
  <xsl:template match="/">
    <html>
      <head>
        <title>
          <xsl:choose>
            <xsl:when test="cda:ClinicalDocument/cda:title">
              <xsl:value-of select="cda:ClinicalDocument/cda:title"/>
            </xsl:when>
            <xsl:otherwise>Clinical Document</xsl:otherwise>
          </xsl:choose>
        </title>
        <style type="text/css">
          body { font-family: 'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif;
                 font-size: 10pt; line-height: 14pt; color: #0F172A; background: #FFFFFF;
                 margin: 0; padding: 0; }
          h1.docTitle { font-size: 17pt; line-height: 21pt; font-weight: normal;
                        color: #0F172A; margin: 0 0 2px 0; }
          .docSubTitle { font-size: 9.5pt; color: #475569; margin: 0 0 10px 0; }
          .Section { page-break-inside: auto; margin: 0 0 10px 0; padding: 0 0 6px 0; }
          .sectionHead { font-size: 13pt; line-height: 17pt; font-weight: normal;
                         color: #0E7490; border-bottom: 1px solid #CBD5E1;
                         margin: 0 0 6px 0; padding: 0 0 3px 0;
                         page-break-after: avoid; page-break-inside: avoid; }
          .sectionBody { padding: 0 0 0 2px; }
          /* The converter's appended metadata section nests an h2 inside
             .sectionHead; normalize it to match native section headings. */
          .sectionHead h2 { font-size: 13pt; line-height: 17pt; font-weight: normal;
                            color: #0E7490; margin: 0; padding: 0; }
          .hdrCard { border: 1px solid #E2E8F0; border-left: 3px solid #0E7490;
                     padding: 8px 10px; margin: 0 0 10px 0; }
          .hdrGrid { width: 100%; border-collapse: collapse; }
          .hdrGrid td { vertical-align: top; padding: 2px 10px 2px 0; font-size: 9.5pt;
                        line-height: 13pt; }
          .hdrLabel { color: #64748B; font-size: 8pt; text-transform: uppercase;
                      letter-spacing: 0.4px; display: block; }
          .hdrValue { color: #0F172A; }
          /* CDA NarrativeBlock rendering */
          .cdaText table { border-collapse: collapse; width: 100%; margin: 4px 0 8px 0;
                           font-size: 9pt; line-height: 12.5pt; }
          .cdaText th { background: #F1F5F9; color: #1E293B; font-weight: bold;
                        text-align: left; border: 1px solid #CBD5E1; padding: 4px 6px;
                        vertical-align: top; }
          .cdaText td { border: 1px solid #CBD5E1; padding: 4px 6px; vertical-align: top;
                        word-break: break-word; }
          .cdaText tr { page-break-inside: avoid; }
          .cdaText thead { display: table-header-group; }
          .cdaText caption { font-weight: bold; text-align: left; padding: 3px 0;
                             color: #334155; }
          .cdaText p { margin: 0 0 6px 0; }
          .cdaText ul, .cdaText ol { margin: 2px 0 6px 0; padding-left: 22px; }
          .cdaText li { margin: 0 0 2px 0; }
          .cdaText .cdaBold { font-weight: bold; }
          .cdaText .cdaItalic { font-style: italic; }
          .cdaText .cdaUnderline { text-decoration: underline; }
          .cdaText .cdaEmphasis { font-weight: bold; }
          .footnote { font-size: 8.5pt; color: #475569; border-left: 2px solid #CBD5E1;
                      padding-left: 6px; margin: 4px 0; }
          .revised-insert { background: #ECFDF5; }
          .revised-delete { text-decoration: line-through; color: #94A3B8; }
          .multimediaRef { font-size: 8.5pt; color: #64748B; font-style: italic; }
          .noData { color: #64748B; font-style: italic; }
        </style>
      </head>
      <body>
        <xsl:apply-templates select="cda:ClinicalDocument"/>
      </body>
    </html>
  </xsl:template>

  <!-- ==================================================================== -->
  <!-- ClinicalDocument                                                     -->
  <!-- ==================================================================== -->
  <xsl:template match="cda:ClinicalDocument">
    <!--
      The #DocWrapper and #DocBody container IDs are integration hooks that
      cda2pdf's converter looks for: it inserts the per-document banner at the
      top of #DocWrapper and appends the "XML Header & Coded Clinical Entries
      Metadata" table to the end of #DocBody. Any replacement stylesheet passed
      via the "xsl" CLI option should emit these two IDs to keep those
      features working.
    -->
    <div id="DocWrapper">
      <h1 class="docTitle">
        <xsl:choose>
          <xsl:when test="cda:title"><xsl:value-of select="cda:title"/></xsl:when>
          <xsl:otherwise>Clinical Document</xsl:otherwise>
        </xsl:choose>
      </h1>
      <div class="docSubTitle">
        <xsl:if test="cda:effectiveTime/@value">
          <xsl:text>Document date: </xsl:text>
          <xsl:call-template name="format-ts">
            <xsl:with-param name="ts" select="cda:effectiveTime/@value"/>
          </xsl:call-template>
        </xsl:if>
      </div>

      <div id="DocBody">
        <xsl:call-template name="patient-header"/>
        <xsl:call-template name="document-header"/>
        <xsl:call-template name="encounter-header"/>

        <xsl:choose>
          <xsl:when test="cda:component/cda:structuredBody">
            <xsl:apply-templates
              select="cda:component/cda:structuredBody/cda:component/cda:section"/>
          </xsl:when>
          <xsl:when test="cda:component/cda:nonXMLBody">
            <div class="Section">
              <div class="sectionHead">Document Body</div>
              <div class="sectionBody noData">
                This document has a nonXMLBody (media type
                <xsl:value-of select="cda:component/cda:nonXMLBody/cda:text/@mediaType"/>)
                which cannot be rendered as narrative text.
              </div>
            </div>
          </xsl:when>
        </xsl:choose>
      </div>
    </div>
  </xsl:template>

  <!-- ==================================================================== -->
  <!-- Patient demographics (recordTarget/patientRole)                      -->
  <!-- ==================================================================== -->
  <xsl:template name="patient-header">
    <xsl:variable name="pr" select="cda:recordTarget/cda:patientRole"/>
    <div class="Section">
      <div class="sectionHead">Patient Demographics</div>
      <div class="hdrCard">
        <table class="hdrGrid">
          <tr>
            <td style="width:34%">
              <span class="hdrLabel">Name</span>
              <span class="hdrValue">
                <xsl:for-each select="$pr/cda:patient/cda:name">
                  <xsl:if test="position() &gt; 1"><br/></xsl:if>
                  <xsl:call-template name="render-name"/>
                </xsl:for-each>
                <xsl:if test="not($pr/cda:patient/cda:name)">
                  <span class="noData">Not recorded</span>
                </xsl:if>
              </span>
            </td>
            <td style="width:33%">
              <span class="hdrLabel">Date of Birth</span>
              <span class="hdrValue">
                <xsl:choose>
                  <xsl:when test="$pr/cda:patient/cda:birthTime/@value">
                    <xsl:call-template name="format-date">
                      <xsl:with-param name="ts" select="$pr/cda:patient/cda:birthTime/@value"/>
                    </xsl:call-template>
                  </xsl:when>
                  <xsl:otherwise><span class="noData">Not recorded</span></xsl:otherwise>
                </xsl:choose>
              </span>
            </td>
            <td style="width:33%">
              <span class="hdrLabel">Sex</span>
              <span class="hdrValue">
                <xsl:call-template name="code-display">
                  <xsl:with-param name="node" select="$pr/cda:patient/cda:administrativeGenderCode"/>
                </xsl:call-template>
              </span>
            </td>
          </tr>
          <tr>
            <td>
              <span class="hdrLabel">Address</span>
              <span class="hdrValue">
                <xsl:variable name="addrs"
                              select="$pr/cda:addr[normalize-space(.) != '']"/>
                <xsl:for-each select="$addrs">
                  <xsl:if test="position() &gt; 1"><br/><br/></xsl:if>
                  <xsl:call-template name="render-addr"/>
                </xsl:for-each>
                <xsl:if test="not($addrs)">
                  <span class="noData">Not recorded</span>
                </xsl:if>
              </span>
            </td>
            <td>
              <span class="hdrLabel">Contact</span>
              <span class="hdrValue">
                <xsl:for-each select="$pr/cda:telecom">
                  <xsl:if test="position() &gt; 1"><br/></xsl:if>
                  <xsl:call-template name="render-telecom"/>
                </xsl:for-each>
                <xsl:if test="not($pr/cda:telecom)">
                  <span class="noData">Not recorded</span>
                </xsl:if>
              </span>
            </td>
            <td>
              <span class="hdrLabel">Patient Identifiers</span>
              <span class="hdrValue">
                <xsl:for-each select="$pr/cda:id">
                  <xsl:if test="position() &gt; 1"><br/></xsl:if>
                  <xsl:value-of select="@extension"/>
                  <xsl:if test="@root">
                    <xsl:text> (root </xsl:text><xsl:value-of select="@root"/><xsl:text>)</xsl:text>
                  </xsl:if>
                </xsl:for-each>
                <xsl:if test="not($pr/cda:id)">
                  <span class="noData">Not recorded</span>
                </xsl:if>
              </span>
            </td>
          </tr>
          <tr>
            <td>
              <span class="hdrLabel">Language</span>
              <span class="hdrValue">
                <xsl:for-each select="$pr/cda:patient/cda:languageCommunication">
                  <xsl:if test="position() &gt; 1">, </xsl:if>
                  <xsl:value-of select="cda:languageCode/@code"/>
                  <xsl:if test="cda:preferenceInd/@value='true'"> (preferred)</xsl:if>
                </xsl:for-each>
                <xsl:if test="not($pr/cda:patient/cda:languageCommunication)">
                  <span class="noData">Not recorded</span>
                </xsl:if>
              </span>
            </td>
            <td>
              <span class="hdrLabel">Race / Ethnicity</span>
              <span class="hdrValue">
                <xsl:call-template name="code-display">
                  <xsl:with-param name="node" select="$pr/cda:patient/cda:raceCode"/>
                </xsl:call-template>
                <xsl:text> / </xsl:text>
                <xsl:call-template name="code-display">
                  <xsl:with-param name="node" select="$pr/cda:patient/cda:ethnicGroupCode"/>
                </xsl:call-template>
              </span>
            </td>
            <td>
              <span class="hdrLabel">Marital Status</span>
              <span class="hdrValue">
                <xsl:call-template name="code-display">
                  <xsl:with-param name="node" select="$pr/cda:patient/cda:maritalStatusCode"/>
                </xsl:call-template>
              </span>
            </td>
          </tr>
        </table>
      </div>
    </div>
  </xsl:template>

  <!-- ==================================================================== -->
  <!-- Document metadata: author, custodian, legal authenticator            -->
  <!-- ==================================================================== -->
  <xsl:template name="document-header">
    <div class="Section">
      <div class="sectionHead">Document Information</div>
      <div class="hdrCard">
        <table class="hdrGrid">
          <tr>
            <td style="width:34%">
              <span class="hdrLabel">Author</span>
              <span class="hdrValue">
                <xsl:for-each select="cda:author">
                  <xsl:if test="position() &gt; 1"><br/></xsl:if>
                  <xsl:choose>
                    <xsl:when test="cda:assignedAuthor/cda:assignedPerson/cda:name">
                      <xsl:for-each select="cda:assignedAuthor/cda:assignedPerson/cda:name[1]">
                        <xsl:call-template name="render-name"/>
                      </xsl:for-each>
                    </xsl:when>
                    <xsl:when test="cda:assignedAuthor/cda:assignedAuthoringDevice">
                      <xsl:value-of
                        select="cda:assignedAuthor/cda:assignedAuthoringDevice/cda:softwareName"/>
                    </xsl:when>
                    <xsl:when test="cda:assignedAuthor/cda:representedOrganization/cda:name">
                      <xsl:value-of
                        select="cda:assignedAuthor/cda:representedOrganization/cda:name"/>
                    </xsl:when>
                    <xsl:otherwise><span class="noData">Not recorded</span></xsl:otherwise>
                  </xsl:choose>
                  <xsl:if test="cda:time/@value">
                    <xsl:text> — </xsl:text>
                    <xsl:call-template name="format-ts">
                      <xsl:with-param name="ts" select="cda:time/@value"/>
                    </xsl:call-template>
                  </xsl:if>
                </xsl:for-each>
                <xsl:if test="not(cda:author)">
                  <span class="noData">Not recorded</span>
                </xsl:if>
              </span>
            </td>
            <td style="width:33%">
              <span class="hdrLabel">Custodian</span>
              <span class="hdrValue">
                <xsl:choose>
                  <xsl:when
                    test="cda:custodian/cda:assignedCustodian/cda:representedCustodianOrganization/cda:name">
                    <xsl:value-of
                      select="cda:custodian/cda:assignedCustodian/cda:representedCustodianOrganization/cda:name"/>
                  </xsl:when>
                  <xsl:otherwise><span class="noData">Not recorded</span></xsl:otherwise>
                </xsl:choose>
              </span>
            </td>
            <td style="width:33%">
              <span class="hdrLabel">Document Type</span>
              <span class="hdrValue">
                <xsl:call-template name="code-display">
                  <xsl:with-param name="node" select="cda:code"/>
                </xsl:call-template>
              </span>
            </td>
          </tr>
          <xsl:if test="cda:legalAuthenticator">
            <tr>
              <td colspan="3">
                <span class="hdrLabel">Legal Authenticator</span>
                <span class="hdrValue">
                  <xsl:for-each
                    select="cda:legalAuthenticator/cda:assignedEntity/cda:assignedPerson/cda:name[1]">
                    <xsl:call-template name="render-name"/>
                  </xsl:for-each>
                  <xsl:if test="cda:legalAuthenticator/cda:time/@value">
                    <xsl:text> — </xsl:text>
                    <xsl:call-template name="format-ts">
                      <xsl:with-param name="ts" select="cda:legalAuthenticator/cda:time/@value"/>
                    </xsl:call-template>
                  </xsl:if>
                </span>
              </td>
            </tr>
          </xsl:if>
        </table>
      </div>
    </div>
  </xsl:template>

  <!-- ==================================================================== -->
  <!-- Encompassing encounter (componentOf)                                 -->
  <!-- ==================================================================== -->
  <xsl:template name="encounter-header">
    <xsl:variable name="enc" select="cda:componentOf/cda:encompassingEncounter"/>
    <xsl:if test="$enc">
      <div class="Section">
        <div class="sectionHead">Encounter</div>
        <div class="hdrCard">
          <table class="hdrGrid">
            <tr>
              <td style="width:34%">
                <span class="hdrLabel">Type</span>
                <span class="hdrValue">
                  <xsl:call-template name="code-display">
                    <xsl:with-param name="node" select="$enc/cda:code"/>
                  </xsl:call-template>
                </span>
              </td>
              <td style="width:33%">
                <span class="hdrLabel">Date</span>
                <span class="hdrValue">
                  <xsl:choose>
                    <xsl:when test="$enc/cda:effectiveTime/cda:low/@value">
                      <xsl:call-template name="format-ts">
                        <xsl:with-param name="ts" select="$enc/cda:effectiveTime/cda:low/@value"/>
                      </xsl:call-template>
                      <xsl:if test="$enc/cda:effectiveTime/cda:high/@value">
                        <xsl:text> to </xsl:text>
                        <xsl:call-template name="format-ts">
                          <xsl:with-param name="ts" select="$enc/cda:effectiveTime/cda:high/@value"/>
                        </xsl:call-template>
                      </xsl:if>
                    </xsl:when>
                    <xsl:when test="$enc/cda:effectiveTime/@value">
                      <xsl:call-template name="format-ts">
                        <xsl:with-param name="ts" select="$enc/cda:effectiveTime/@value"/>
                      </xsl:call-template>
                    </xsl:when>
                    <xsl:otherwise><span class="noData">Not recorded</span></xsl:otherwise>
                  </xsl:choose>
                </span>
              </td>
              <td style="width:33%">
                <span class="hdrLabel">Location</span>
                <span class="hdrValue">
                  <xsl:choose>
                    <xsl:when
                      test="$enc/cda:location/cda:healthCareFacility/cda:location/cda:name">
                      <xsl:value-of
                        select="$enc/cda:location/cda:healthCareFacility/cda:location/cda:name"/>
                    </xsl:when>
                    <xsl:when
                      test="$enc/cda:location/cda:healthCareFacility/cda:serviceProviderOrganization/cda:name">
                      <xsl:value-of
                        select="$enc/cda:location/cda:healthCareFacility/cda:serviceProviderOrganization/cda:name"/>
                    </xsl:when>
                    <xsl:otherwise><span class="noData">Not recorded</span></xsl:otherwise>
                  </xsl:choose>
                </span>
              </td>
            </tr>
          </table>
        </div>
      </div>
    </xsl:if>
  </xsl:template>

  <!-- ==================================================================== -->
  <!-- Sections (recursive: supports nested component/section)              -->
  <!-- ==================================================================== -->
  <xsl:template match="cda:section">
    <div class="Section">
      <xsl:if test="cda:title">
        <div class="sectionHead"><xsl:value-of select="cda:title"/></div>
      </xsl:if>
      <div class="sectionBody">
        <xsl:choose>
          <xsl:when test="cda:text">
            <div class="cdaText"><xsl:apply-templates select="cda:text"/></div>
          </xsl:when>
          <xsl:otherwise>
            <div class="noData">No narrative text recorded for this section.</div>
          </xsl:otherwise>
        </xsl:choose>
        <xsl:apply-templates select="cda:component/cda:section"/>
      </div>
    </div>
  </xsl:template>

  <!-- ==================================================================== -->
  <!-- CDA R2 NarrativeBlock                                                -->
  <!-- Per the CDA R2 schema, <text> may contain: paragraph, list, table,   -->
  <!-- content, linkHtml, sub, sup, br, footnote, footnoteRef,              -->
  <!-- renderMultiMedia, caption.                                           -->
  <!-- ==================================================================== -->

  <xsl:template match="cda:text">
    <xsl:apply-templates mode="nb"/>
  </xsl:template>

  <xsl:template match="cda:paragraph" mode="nb">
    <p><xsl:call-template name="nb-styleCode"/><xsl:apply-templates mode="nb"/></p>
  </xsl:template>

  <xsl:template match="cda:br" mode="nb">
    <br/>
  </xsl:template>

  <!-- content: inline span; carries ID targets referenced by coded entries -->
  <xsl:template match="cda:content" mode="nb">
    <span>
      <xsl:if test="@ID"><xsl:attribute name="id"><xsl:value-of select="@ID"/></xsl:attribute></xsl:if>
      <xsl:call-template name="nb-styleCode"/>
      <xsl:apply-templates mode="nb"/>
    </span>
  </xsl:template>

  <xsl:template match="cda:sub" mode="nb"><sub><xsl:apply-templates mode="nb"/></sub></xsl:template>
  <xsl:template match="cda:sup" mode="nb"><sup><xsl:apply-templates mode="nb"/></sup></xsl:template>

  <xsl:template match="cda:linkHtml" mode="nb">
    <a>
      <xsl:if test="@href"><xsl:attribute name="href"><xsl:value-of select="@href"/></xsl:attribute></xsl:if>
      <xsl:apply-templates mode="nb"/>
    </a>
  </xsl:template>

  <xsl:template match="cda:list" mode="nb">
    <xsl:if test="cda:caption">
      <div class="cdaBold"><xsl:apply-templates select="cda:caption" mode="nb"/></div>
    </xsl:if>
    <xsl:choose>
      <xsl:when test="@listType='ordered'">
        <ol><xsl:apply-templates select="cda:item" mode="nb"/></ol>
      </xsl:when>
      <xsl:otherwise>
        <ul><xsl:apply-templates select="cda:item" mode="nb"/></ul>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="cda:item" mode="nb">
    <li><xsl:call-template name="nb-styleCode"/><xsl:apply-templates mode="nb"/></li>
  </xsl:template>

  <xsl:template match="cda:caption" mode="nb">
    <caption><xsl:apply-templates mode="nb"/></caption>
  </xsl:template>

  <xsl:template match="cda:footnote" mode="nb">
    <div class="footnote"><xsl:apply-templates mode="nb"/></div>
  </xsl:template>

  <xsl:template match="cda:footnoteRef" mode="nb">
    <sup class="multimediaRef">
      <xsl:text>[</xsl:text><xsl:value-of select="@IDREF"/><xsl:text>]</xsl:text>
    </sup>
  </xsl:template>

  <xsl:template match="cda:renderMultiMedia" mode="nb">
    <div class="multimediaRef">
      <xsl:text>[Referenced media: </xsl:text>
      <xsl:value-of select="@referencedObject"/>
      <xsl:text>]</xsl:text>
    </div>
  </xsl:template>

  <!-- Tables: the CDA narrative table model mirrors the XHTML subset. -->
  <xsl:template match="cda:table" mode="nb">
    <table><xsl:call-template name="nb-copy-table-attrs"/><xsl:apply-templates mode="nb"/></table>
  </xsl:template>
  <xsl:template match="cda:thead" mode="nb"><thead><xsl:apply-templates mode="nb"/></thead></xsl:template>
  <xsl:template match="cda:tbody" mode="nb"><tbody><xsl:apply-templates mode="nb"/></tbody></xsl:template>
  <xsl:template match="cda:tfoot" mode="nb"><tfoot><xsl:apply-templates mode="nb"/></tfoot></xsl:template>
  <xsl:template match="cda:colgroup" mode="nb"><colgroup><xsl:apply-templates mode="nb"/></colgroup></xsl:template>
  <xsl:template match="cda:col" mode="nb"><col><xsl:call-template name="nb-copy-table-attrs"/></col></xsl:template>
  <xsl:template match="cda:tr" mode="nb">
    <tr><xsl:call-template name="nb-copy-table-attrs"/><xsl:apply-templates mode="nb"/></tr>
  </xsl:template>
  <xsl:template match="cda:th" mode="nb">
    <th><xsl:call-template name="nb-copy-table-attrs"/><xsl:apply-templates mode="nb"/></th>
  </xsl:template>
  <xsl:template match="cda:td" mode="nb">
    <td><xsl:call-template name="nb-copy-table-attrs"/><xsl:apply-templates mode="nb"/></td>
  </xsl:template>

  <xsl:template name="nb-copy-table-attrs">
    <xsl:copy-of select="@colspan|@rowspan|@align|@valign|@span|@width|@scope|@abbr|@headers"/>
  </xsl:template>

  <!-- styleCode: CDA defines Bold/Italics/Underline/Emphasis plus table rules. -->
  <xsl:template name="nb-styleCode">
    <xsl:if test="@styleCode">
      <xsl:attribute name="class">
        <xsl:if test="contains(@styleCode, 'Bold')">cdaBold </xsl:if>
        <xsl:if test="contains(@styleCode, 'Italics')">cdaItalic </xsl:if>
        <xsl:if test="contains(@styleCode, 'Underline')">cdaUnderline </xsl:if>
        <xsl:if test="contains(@styleCode, 'Emphasis')">cdaEmphasis </xsl:if>
      </xsl:attribute>
    </xsl:if>
    <xsl:if test="@revised='insert'">
      <xsl:attribute name="class">revised-insert</xsl:attribute>
    </xsl:if>
    <xsl:if test="@revised='delete'">
      <xsl:attribute name="class">revised-delete</xsl:attribute>
    </xsl:if>
  </xsl:template>

  <!-- Preserve text nodes verbatim; drop unknown elements but keep their text. -->
  <xsl:template match="text()" mode="nb"><xsl:value-of select="."/></xsl:template>
  <xsl:template match="*" mode="nb"><xsl:apply-templates mode="nb"/></xsl:template>

  <!-- ==================================================================== -->
  <!-- Shared helpers                                                       -->
  <!-- ==================================================================== -->

  <!-- Render a PN (person name): given/family, or mixed content fallback. -->
  <xsl:template name="render-name">
    <xsl:choose>
      <xsl:when test="cda:given or cda:family">
        <xsl:for-each select="cda:prefix">
          <xsl:value-of select="."/><xsl:text> </xsl:text>
        </xsl:for-each>
        <xsl:for-each select="cda:given">
          <xsl:value-of select="."/><xsl:text> </xsl:text>
        </xsl:for-each>
        <xsl:value-of select="cda:family"/>
        <xsl:for-each select="cda:suffix">
          <xsl:text> </xsl:text><xsl:value-of select="."/>
        </xsl:for-each>
      </xsl:when>
      <xsl:otherwise><xsl:value-of select="normalize-space(.)"/></xsl:otherwise>
    </xsl:choose>
    <xsl:if test="@use='L'"> </xsl:if>
  </xsl:template>

  <!-- Render an AD (postal address). -->
  <xsl:template name="render-addr">
    <xsl:for-each select="cda:streetAddressLine[normalize-space(.)]">
      <xsl:value-of select="."/><br/>
    </xsl:for-each>
    <!-- Emit separators only between parts that are actually present, so an
         address carrying just a country does not render as ", USA". -->
    <xsl:variable name="city" select="normalize-space(cda:city)"/>
    <xsl:variable name="state" select="normalize-space(cda:state)"/>
    <xsl:variable name="zip" select="normalize-space(cda:postalCode)"/>
    <xsl:variable name="country" select="normalize-space(cda:country)"/>
    <xsl:value-of select="$city"/>
    <xsl:if test="$state">
      <xsl:if test="$city"><xsl:text>, </xsl:text></xsl:if>
      <xsl:value-of select="$state"/>
    </xsl:if>
    <xsl:if test="$zip">
      <xsl:if test="$city or $state"><xsl:text> </xsl:text></xsl:if>
      <xsl:value-of select="$zip"/>
    </xsl:if>
    <xsl:if test="$country">
      <xsl:if test="$city or $state or $zip"><xsl:text> </xsl:text></xsl:if>
      <xsl:value-of select="$country"/>
    </xsl:if>
    <xsl:if test="@use and ($city or $state or $zip or $country
                            or cda:streetAddressLine[normalize-space(.)])">
      <xsl:text> (</xsl:text>
      <xsl:call-template name="use-label"><xsl:with-param name="use" select="@use"/></xsl:call-template>
      <xsl:text>)</xsl:text>
    </xsl:if>
  </xsl:template>

  <!-- Render a TEL (telecom), stripping the URI scheme. -->
  <xsl:template name="render-telecom">
    <xsl:variable name="v" select="@value"/>
    <xsl:choose>
      <xsl:when test="starts-with($v, 'tel:')"><xsl:value-of select="substring-after($v, 'tel:')"/></xsl:when>
      <xsl:when test="starts-with($v, 'mailto:')"><xsl:value-of select="substring-after($v, 'mailto:')"/></xsl:when>
      <xsl:when test="starts-with($v, 'fax:')"><xsl:value-of select="substring-after($v, 'fax:')"/></xsl:when>
      <xsl:otherwise><xsl:value-of select="$v"/></xsl:otherwise>
    </xsl:choose>
    <xsl:if test="@use">
      <xsl:text> (</xsl:text>
      <xsl:call-template name="use-label"><xsl:with-param name="use" select="@use"/></xsl:call-template>
      <xsl:text>)</xsl:text>
    </xsl:if>
  </xsl:template>

  <!-- HL7 AddressUse / TelecommunicationAddressUse codes. -->
  <xsl:template name="use-label">
    <xsl:param name="use"/>
    <xsl:choose>
      <xsl:when test="$use='H'">Home</xsl:when>
      <xsl:when test="$use='HP'">Home</xsl:when>
      <xsl:when test="$use='HV'">Vacation Home</xsl:when>
      <xsl:when test="$use='WP'">Work</xsl:when>
      <xsl:when test="$use='MC'">Mobile</xsl:when>
      <xsl:when test="$use='TMP'">Temporary</xsl:when>
      <xsl:when test="$use='OLD'">Former</xsl:when>
      <xsl:when test="$use='BAD'">Former</xsl:when>
      <xsl:when test="$use='PUB'">Public</xsl:when>
      <xsl:when test="$use='EC'">Emergency Contact</xsl:when>
      <xsl:otherwise><xsl:value-of select="$use"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- Display a CD/CE: prefer displayName, then originalText, then code. -->
  <xsl:template name="code-display">
    <xsl:param name="node"/>
    <xsl:choose>
      <xsl:when test="not($node)"><span class="noData">Not recorded</span></xsl:when>
      <xsl:when test="$node/@displayName"><xsl:value-of select="$node/@displayName"/></xsl:when>
      <xsl:when test="$node/cda:originalText"><xsl:value-of select="$node/cda:originalText"/></xsl:when>
      <xsl:when test="$node/@code"><xsl:value-of select="$node/@code"/></xsl:when>
      <xsl:otherwise><span class="noData">Not recorded</span></xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- Format HL7 TS (YYYYMMDDHHMMSS[+-]ZZZZ) as YYYY-MM-DD HH:MM. -->
  <xsl:template name="format-ts">
    <xsl:param name="ts"/>
    <xsl:variable name="t" select="normalize-space($ts)"/>
    <xsl:if test="string-length($t) &gt;= 8">
      <xsl:value-of select="substring($t,1,4)"/>
      <xsl:text>-</xsl:text>
      <xsl:value-of select="substring($t,5,2)"/>
      <xsl:text>-</xsl:text>
      <xsl:value-of select="substring($t,7,2)"/>
    </xsl:if>
    <xsl:if test="string-length($t) &gt;= 12">
      <xsl:text> </xsl:text>
      <xsl:value-of select="substring($t,9,2)"/>
      <xsl:text>:</xsl:text>
      <xsl:value-of select="substring($t,11,2)"/>
    </xsl:if>
    <xsl:if test="string-length($t) &lt; 8"><xsl:value-of select="$t"/></xsl:if>
  </xsl:template>

  <!-- Format HL7 TS as a date only. -->
  <xsl:template name="format-date">
    <xsl:param name="ts"/>
    <xsl:variable name="t" select="normalize-space($ts)"/>
    <xsl:choose>
      <xsl:when test="string-length($t) &gt;= 8">
        <xsl:value-of select="substring($t,1,4)"/>
        <xsl:text>-</xsl:text>
        <xsl:value-of select="substring($t,5,2)"/>
        <xsl:text>-</xsl:text>
        <xsl:value-of select="substring($t,7,2)"/>
      </xsl:when>
      <xsl:otherwise><xsl:value-of select="$t"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>

</xsl:stylesheet>
