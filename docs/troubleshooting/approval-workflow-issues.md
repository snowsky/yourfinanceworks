# Approval Workflow Troubleshooting Guide

## Overview

This guide helps users and administrators diagnose and resolve common issues with the expense approval workflow. Issues are organized by user type and symptom for quick resolution.

## For Employees: Submission Issues

### Cannot Submit Expense for Approval

**Symptoms:**
- "Submit for Approval" button is disabled or missing
- Error message when trying to submit
- Expense remains in draft status

**Common Causes & Solutions:**

#### Missing Required Information
**Problem:** Required fields are not completed
**Solution:**
1. Check for red asterisks (*) indicating required fields
2. Ensure all mandatory fields have values:
   - Amount (must be greater than $0)
   - Date (cannot be future date beyond policy limit)
   - Category (must be selected from dropdown)
   - Description (minimum character requirement)
   - Receipt (if required by policy)
3. Upload clear, legible receipts
4. Verify expense date is within submission deadline

#### Expense Amount Issues
**Problem:** Amount violates policy limits
**Solution:**
1. Check if amount exceeds your approval limit
2. Verify amount is in correct currency
3. Ensure decimal places are correct (e.g., 150.00 not 15000)
4. Split large expenses if allowed by policy
5. Contact manager if legitimate business expense exceeds limits

#### Technical Issues
**Problem:** System errors during submission
**Solution:**
1. Refresh the page and try again
2. Clear browser cache and cookies
3. Try a different browser
4. Check internet connection
5. Contact IT support if problem persists

### Expense Stuck in "Pending Approval"

**Symptoms:**
- Expense shows "Pending Approval" for extended period
- No approval activity in expense history
- Approver claims they never received notification

**Troubleshooting Steps:**

1. **Check Current Approver**
   - View expense details to see assigned approver
   - Verify approver is correct person for your expense type/amount
   - Check if approver has active delegation

2. **Verify Approver Availability**
   - Contact approver directly to confirm they received notification
   - Check if approver is out of office or on leave
   - Ask if they need additional information

3. **Check Notification Settings**
   - Verify approver's email address is correct
   - Check if approval emails are going to spam folder
   - Confirm notification preferences are enabled

4. **Escalation Process**
   - Wait for automatic escalation (if configured)
   - Contact approver's manager if urgent
   - Reach out to HR or Finance for assistance

### Expense Rejected - What to Do

**Symptoms:**
- Expense status shows "Rejected"
- Rejection reason provided by approver
- Cannot edit expense details

**Resolution Steps:**

1. **Review Rejection Reason**
   - Read the detailed feedback from approver
   - Understand what needs to be corrected
   - Check if additional documentation is needed

2. **Make Necessary Corrections**
   - Address all issues mentioned in rejection
   - Gather additional receipts or documentation
   - Correct any policy violations

3. **Resubmit Process**
   - Click "Resubmit" button on rejected expense
   - Make required changes in the resubmission form
   - Add notes explaining corrections made
   - Upload any additional documentation

4. **Prevent Future Rejections**
   - Review expense policy guidelines
   - Double-check requirements before submission
   - Contact manager for clarification on unclear policies

## For Managers: Approval Issues

### Cannot See Pending Approvals

**Symptoms:**
- Approval dashboard shows no pending items
- Employees report submitting expenses for your approval
- Missing approval notifications

**Troubleshooting Steps:**

1. **Check Approval Permissions**
   - Verify you have approval permissions in the system
   - Confirm your approval limits are correctly configured
   - Check if your role includes approval responsibilities

2. **Review Filter Settings**
   - Clear any active filters on approval dashboard
   - Check date range settings
   - Verify you're looking at correct expense categories

3. **Check Delegation Status**
   - Verify if you have active delegation settings
   - Confirm delegation hasn't automatically taken over approvals
   - Review delegation scope and dates

4. **System Configuration Issues**
   - Contact administrator to verify approval rule configuration
   - Check if organizational hierarchy is correctly set up
   - Ensure your user profile is properly configured

### Cannot Approve/Reject Expenses

**Symptoms:**
- Approve/Reject buttons are disabled
- Error messages when trying to make decisions
- "Insufficient permissions" errors

**Common Solutions:**

1. **Permission Issues**
   - Verify expense amount is within your approval limit
   - Check if expense category requires special permissions
   - Confirm you're the assigned approver for this expense

2. **Expense Status Problems**
   - Ensure expense hasn't already been approved/rejected
   - Check if expense is at correct approval level
   - Verify expense hasn't been withdrawn by employee

3. **Technical Issues**
   - Refresh browser and try again
   - Clear browser cache
   - Try different browser or device
   - Check for system maintenance notifications

### Approval Notifications Not Working

**Symptoms:**
- Not receiving email notifications for new approvals
- Delayed notification delivery
- Missing reminder notifications

**Resolution Steps:**

1. **Check Email Settings**
   - Verify email address in user profile
   - Check spam/junk folders for approval emails
   - Confirm email client isn't blocking system emails

2. **Notification Preferences**
   - Review notification settings in user preferences
   - Ensure approval notifications are enabled
   - Check frequency settings (immediate vs. digest)

3. **System Issues**
   - Contact IT support to check email delivery logs
   - Verify system notification service is operational
   - Check for email server issues

## For Administrators: Configuration Issues

### Approval Rules Not Working

**Symptoms:**
- Expenses not routing to correct approvers
- Wrong approval levels being assigned
- Auto-approval not functioning

**Diagnostic Steps:**

1. **Rule Evaluation Testing**
   - Use rule simulator to test expense scenarios
   - Check rule priority ordering
   - Verify amount ranges don't have gaps

2. **Rule Configuration Review**
   - Ensure rules are marked as active
   - Check category filters are correctly specified
   - Verify approver assignments are valid

3. **Conflict Resolution**
   - Identify overlapping rules
   - Resolve priority conflicts
   - Document rule precedence logic

### Performance Issues

**Symptoms:**
- Slow approval dashboard loading
- Timeout errors during approval submission
- Database performance problems

**Optimization Steps:**

1. **Database Performance**
   - Check approval table indexes
   - Monitor query performance
   - Review database connection pool settings

2. **System Resources**
   - Monitor server CPU and memory usage
   - Check for background job backlogs
   - Review notification queue processing

3. **User Load Management**
   - Implement pagination for large approval lists
   - Add caching for frequently accessed data
   - Optimize approval rule evaluation

### Integration Problems

**Symptoms:**
- Notification emails not sending
- Audit logs not recording properly
- External system synchronization issues

**Resolution Approach:**

1. **Service Dependencies**
   - Check notification service status
   - Verify database connectivity
   - Test external API connections

2. **Configuration Validation**
   - Review service configuration files
   - Check environment variables
   - Validate API credentials

3. **Monitoring and Logging**
   - Enable detailed logging for troubleshooting
   - Set up monitoring alerts
   - Review error logs for patterns

## Common Error Messages

### "No approval rule found for this expense"

**Cause:** Expense doesn't match any configured approval rules
**Solution:**
1. Check if approval rules cover the expense amount range
2. Verify category-specific rules are configured
3. Set up fallback approver for unmatched expenses
4. Review rule priority and activation status

### "Approver not available"

**Cause:** Assigned approver is inactive or doesn't have permissions
**Solution:**
1. Verify approver's user account is active
2. Check approver's permission levels
3. Update approval rules with current approvers
4. Set up delegation or backup approvers

### "Approval deadline exceeded"

**Cause:** Expense has been pending approval too long
**Solution:**
1. Configure automatic escalation rules
2. Set up reminder notifications
3. Implement approval deadline policies
4. Train managers on timely approval processing

### "Invalid approval level"

**Cause:** Approval level mismatch in multi-level workflow
**Solution:**
1. Review multi-level approval rule configuration
2. Check approval level sequencing
3. Verify expense routing logic
4. Test approval workflow end-to-end

## Escalation Procedures

### When to Escalate

- Technical issues persist after basic troubleshooting
- Policy questions require management decision
- System-wide problems affecting multiple users
- Security concerns or suspicious activity

### Escalation Contacts

1. **Level 1 - IT Support**
   - Technical issues
   - User account problems
   - System access issues

2. **Level 2 - System Administrator**
   - Configuration problems
   - Rule setup issues
   - Integration problems

3. **Level 3 - Finance/HR**
   - Policy interpretation
   - Approval authority questions
   - Compliance issues

4. **Level 4 - Management**
   - Policy changes
   - System-wide decisions
   - Budget approval for fixes

## Prevention Best Practices

### For Users
- Keep expense submissions current and complete
- Understand approval policies and limits
- Maintain clear communication with approvers
- Report issues promptly

### For Managers
- Process approvals within policy timeframes
- Set up delegation before planned absences
- Provide clear feedback on rejections
- Stay informed about policy updates

### For Administrators
- Monitor system performance regularly
- Keep approval rules updated
- Test configuration changes thoroughly
- Maintain comprehensive documentation

## Monitoring and Maintenance

### Regular Health Checks

1. **Weekly Reviews**
   - Check approval processing times
   - Review error logs for patterns
   - Monitor notification delivery rates
   - Verify rule effectiveness

2. **Monthly Analysis**
   - Generate approval metrics reports
   - Review user feedback and issues
   - Analyze approval bottlenecks
   - Update documentation as needed

3. **Quarterly Assessments**
   - Review approval rule effectiveness
   - Update policies based on business changes
   - Conduct user satisfaction surveys
   - Plan system improvements

### Proactive Monitoring

- Set up alerts for approval delays
- Monitor system performance metrics
- Track approval success rates
- Watch for unusual approval patterns

## Getting Additional Help

### Documentation Resources
- User Guide: `/docs/user-guide/approval-workflow.md`
- Admin Guide: `/docs/admin-guide/approval-rules-configuration.md`
- API Documentation: `/api/docs/approval_api.md`

### Support Channels
- **Help Desk**: Submit ticket through internal portal
- **Email Support**: [expense-support@company.com](mailto:expense-support@company.com)
- **Phone Support**: Available during business hours
- **Community Forum**: Share solutions with other users

### Training Resources
- New user onboarding materials
- Manager approval training sessions
- Administrator configuration workshops
- Video tutorials and walkthroughs

Remember: When reporting issues, include specific error messages, steps to reproduce the problem, and relevant expense/approval IDs to help support teams resolve issues quickly.