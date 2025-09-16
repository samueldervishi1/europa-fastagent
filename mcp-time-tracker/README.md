# Time Tracker MCP

Custom Model Context Protocol (MCP) server for tracking work hours, managing timers, and generating time reports through Europa FastAgent.

## Features

### Timer Management
- **Start/Stop Timers** - Real-time work tracking
- **Timer Status** - Check current timer and elapsed time
- **Project Categories** - Organize work by type (personal, client, learning, etc.)

### Manual Time Logging
- **Retroactive Entries** - Log time for past work
- **Flexible Duration Input** - Support for "2h", "90m", "1h 30m" formats
- **Project Organization** - Automatic project and category tracking

### Reporting & Analysis
- **Time Summaries** - Daily, weekly, monthly reports
- **Project Tracking** - See total time per project
- **Recent Entries** - View your latest time logs
- **Category Analysis** - Break down time by work type

## Available Commands

### Timer Operations
```bash
maestro > start timer for Europa development
maestro > start timer for client work with description API integration
maestro > stop timer
maestro > what's my current timer status?
```

### Manual Logging
```bash
maestro > log 2 hours of client work yesterday
maestro > log 90 minutes for learning category with description studying React
maestro > log 1h 30m for meeting on 2025-01-15
```

### Reports & Summaries
```bash
maestro > show today's time summary
maestro > get this week's time report
maestro > what projects have I worked on?
maestro > show my recent time entries
```

### Data Management
```bash
maestro > delete last time entry
maestro > list all my projects
```

## Data Storage

### Local JSON File
Time data is stored in `time_tracker_data.json` with the following structure:

```json
{
  "active_timer": {
    "project": "Europa Development",
    "category": "personal",
    "start_time": "2025-01-16T10:30:00",
    "description": "Building time tracker MCP"
  },
  "entries": [
    {
      "id": "uuid-123",
      "project": "Europa Development",
      "category": "personal",
      "start_time": "2025-01-16T09:00:00",
      "end_time": "2025-01-16T11:30:00",
      "duration_minutes": 150,
      "description": "Time tracker implementation",
      "date": "2025-01-16"
    }
  ],
  "projects": ["Europa Development", "Client Work"],
  "categories": ["personal", "client", "learning", "meeting", "other"]
}
```

### Categories
Default categories include:
- **personal** - Personal projects and learning
- **client** - Client work and freelancing
- **learning** - Study, courses, research
- **meeting** - Meetings and calls
- **other** - Miscellaneous work

## Duration Formats

The time tracker supports flexible duration input:

- **Hours**: `2h`, `1.5h`, `0.5h`
- **Minutes**: `90m`, `30m`, `15m`
- **Combined**: `1h 30m`, `2h 15m`
- **Plain Numbers**: `90` (interpreted as minutes)

## Integration with Europa

### Smart Routing
Europa automatically routes time-related requests to the Time Tracker:

**Keywords**: "timer", "time", "hours", "log", "track", "start", "stop", "work", "project", "timesheet", "summary"

### Natural Language Examples
```bash
> "Start timing my Europa development work"
> "How much time have I logged today?"
> "Log 2 hours of client work from yesterday"
> "What projects am I working on?"
> "Stop the current timer"
> "Show me this week's timesheet"
```

## Use Cases

### Freelancers
- Track billable hours per client
- Generate timesheets for invoicing
- Monitor project time allocation

### Developers
- Log development time by feature
- Track learning and research time
- Monitor productivity patterns

### General Productivity
- Time management and awareness
- Project planning and estimation
- Work-life balance monitoring

## Example Workflow

```bash
# Start your day
> start timer for client project ABC

# Work for a while, then take a break
> stop timer
# Logged 2h 15m for 'client project ABC'

# Log some retroactive time
> log 1 hour of learning yesterday with description reading documentation

# Check your progress
> show today's time summary
# Time Summary - Today (2025-01-16)
# Total Time: 3h 15m
#
# By Project:
#   client project ABC: 2h 15m
#   learning: 1h
#
# By Category:
#   client: 2h 15m
#   learning: 1h

# See what you've been working on
> list my projects
# Your Projects:
# client project ABC: 15h 30m
# Europa Development: 8h 45m
# learning: 3h 15m
```

## Tips

1. **Consistent Project Names** - Use the same project name for better reporting
2. **Descriptive Categories** - Choose appropriate categories for better analysis
3. **Regular Logging** - Log time daily for accurate records
4. **Timer Discipline** - Remember to stop timers when taking breaks
5. **Review Reports** - Check weekly summaries to understand time patterns

## Technical Details

- Built with FastMCP framework
- JSON-based local storage
- UUID-based entry tracking
- Timezone-aware datetime handling
- Flexible duration parsing
- Automatic project/category management

## Future Enhancements

Potential features for future versions:
- Export to CSV/Excel
- Time goals and targets
- Productivity insights
- Integration with calendar apps
- Team time tracking
- Invoice generation from logged hours