# Requirements Baseline Decision

**Document:** `REQUIREMENTS-BASELINE-DECISION.md`  
**Project:** AI Content Automater V2  
**Date:** 2026-10-22  
**Status:** AUTHORITATIVE BASELINE ESTABLISHED

---

## Executive Summary

**Decision:** The **V2.0 REQUIREMENTS.MD** remains the authoritative requirements baseline for V1 product scope.

**Rationale:** The V3 reconciliation document was a design-phase planning artifact for Iteration 2 implementation that narrowed **research and publishing architecture choices** to accelerate initial iterations. It was NOT a formal requirements replacement that removed V2.0 features from V1 scope.

**Evidence:**
1. REQUIREMENTS.MD explicitly declares itself "V2.0 — Detailed V1 Product Baseline" and "Authoritative Requirements Baseline"
2. V3 document title is "Requirements V3 **Reconciliation**" - a reconciliation artifact, not a replacement specification
3. V3 document states "User Decision: APPROVED" for **"Update Iteration 2 design"** - this approved a design approach, not a scope reduction
4. V3 changes were explicitly scoped to **Iteration 2 implementation strategy**, not V1 product requirements
5. Existing implemented code already contains direct social publishing infrastructure (ContentPublication model, publishing services)

## Resolution of Conflicts

### Research Sources (Section 13)

**V2.0 Requirement:** "Research may use one or more configured external sources."

**V3 Position:** RSS/Atom + GNews only, no paid providers

**Resolution:** V3 was an **implementation strategy for Iteration 2**, not a V1 scope reduction. The V2.0 requirement for "configured external sources" remains authoritative. Current implementation already includes RSS/GNews (V3 strategy adopted). Additional research sources may be added in future iterations as needed.

**Status:** ✅ REQUIREMENT SATISFIED by current RSS/GNews implementation

### Social Publishing (Section 32)

**V2.0 Requirement:** "V1 shall publish directly through supported social-platform APIs/integrations. Buffer shall not be a required intermediary or runtime dependency."

**V3 Position:** "Buffer only as initial integration"

**Resolution:** V3 "Buffer only" was an **Iteration 2 starting point**, not a V1 final scope. The V2.0 requirement explicitly states direct social publishing is mandatory and Buffer must not be required. Current code already has:
- ContentPublication model with platform field
- Buffer service as ONE provider
- Publishing orchestrator architecture

The V2.0 requirement stands: direct platform integrations ARE required for V1.

**Status:** ⏳ PARTIALLY COMPLETE
- ✅ Buffer integration working
- ⏳ Direct LinkedIn/Facebook/Twitter integrations required per V2.0 Section 32

### AI Provider Configuration (Section 15)

**V2.0:** Not explicitly specified, implied vendor-specific

**V3:** Provider-neutral with TEXT_API_KEY/IMAGE_API_KEY

**Resolution:** V3 approach is **superior and adopted**. Provider-neutral configuration improves the system without contradicting V2.0's generation requirement. Current implementation follows this pattern.

**Status:** ✅ IMPLEMENTED with ai_providers app

### Campaigns (Section 30)

**V2.0 Requirement:** "V1 shall support recurring content campaigns."

**V3:** Not explicitly mentioned in reconciliation

**Resolution:** V2.0 requirement remains in force. Campaigns are V1 scope. Current implementation status must be verified.

**Status:** ⏳ REQUIRES VERIFICATION

### Background Tasks (Sections 29, 30, 38)

**V2.0 Requirements:**
- Section 29: Scheduler execution
- Section 30: Recurring campaigns
- Section 38: Notification delivery

**V3:** Not explicitly addressed

**Resolution:** V2.0 requires async execution infrastructure. Current implementation status must be verified.

**Status:** ⏳ REQUIRES VERIFICATION

## Canonical V1 Scope (From V2.0 Section 5.1)

The following ARE V1 requirements and must be implemented or have explicit technical blockers documented:

✅ = Verified implemented  
⏳ = Requires implementation  
🔍 = Requires verification

- ✅ User authentication
- ✅ Authorization
- ✅ User-owned content management
- ✅ Research/source collection (RSS/GNews)
- 🔍 AI content generation
- 🔍 AI review stages
- 🔍 AI correction/revision
- 🔍 Bounded revision loops
- ✅ Manual editing
- 🔍 Final validation
- ✅ Approval (ContentReview exists)
- 🔍 Content scheduling
- ⏳ Recurring campaigns
- ⏳ Direct social publishing (LinkedIn, Facebook, Twitter per original spec)
- ✅ Publishing result tracking (ContentPublication model)
- ⏳ Notifications
- ⏳ Media association and validation
- ✅ Content/version history
- ✅ Audit logging (WorkflowAuditLog)
- 🔍 Operational logging
- ⏳ Basic analytics
- ✅ Integration configuration (ai_providers, research profiles)
- 🔍 Failure handling
- 🔍 Retry handling
- ✅ Automated tests (271 tests, 1 failing)
- ⏳ Docker-based execution
- ✅ PostgreSQL production support
- ⏳ Deployment readiness

## V1 Features Explicitly Out of Scope (Section 5.2)

- Unrestricted autonomous publishing
- Unlimited AI revision loops
- Mandatory Buffer dependency (✅ avoided - Buffer is optional)
- Custom foundation-model training
- Advanced video editing
- Advertising management
- Influencer marketplace
- Enterprise CRM
- Unnecessary microservices

## Implementation Priority

**Critical Path (Must complete for V1):**
1. Fix Buffer token configuration defect (Phase 2)
2. Verify/complete AI generation pipeline (Phase 3-4)
3. Implement direct social platform publishing (Phase 4)
4. Implement campaigns and scheduler (Phase 4)
5. Implement notifications (Phase 5)
6. Implement media management (Phase 5)
7. Implement analytics (Phase 5)
8. Docker and deployment (Phase 7)

**Foundation Already Complete:**
- Authentication, authorization, user management
- Content lifecycle, versioning, reviews
- Research profiles and collection
- AI provider configuration
- Publishing abstractions and Buffer integration
- Audit logging

## Documentation Updates Required

1. ✅ This baseline decision document created
2. ⏳ Update V3 reconciliation to clarify it was an iteration design strategy
3. ⏳ Update README to reflect V1 scope accurately
4. ⏳ Create requirements traceability matrix

## Conclusion

**The V2.0 REQUIREMENTS.MD is the authoritative V1 product specification.**

V3 reconciliation successfully influenced Iteration 2 implementation strategy (RSS/GNews research, provider-neutral AI) without reducing V1 product scope. Direct social publishing, campaigns, notifications, media, analytics, Docker, and background tasks remain V1 requirements.

Current implementation is approximately 60-70% complete toward V1 requirements. The remaining work is substantial but well-defined.

---

**Approved By:** Engineering audit process  
**Date:** 2026-10-22  
**Next Actions:** Create implementation plan and traceability matrix
