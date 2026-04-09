# Revit C# Extension Development Guide

## Project Overview

This is a **Revit plugin** written in **C# using .NET Framework 4.8**. The plugin calculates rain water flow through rain funnels (воронки) on terraces, computes areas, and performs hydraulic calculations to verify pipe capacity.

### Purpose
- Calculate rain water runoff from terrace areas
- Link terraces to rain funnels (воронки) and vertical stacks (стояки)
- Compute flow rates using rain intensity formulas
- Verify if funnels/pipe capacity meets calculated demand
- Group results by stacks and building sections

---

## Architecture Overview

The plugin is divided into three main parts:

### 1. Data Collection (Сбор данных из модели)
Retrieve elements from the BIM model using Revit API:
- **Rooms** (помещения) - for terrace identification
- **PlumbingFixtures** (сантехнические приборы) - for rain funnels
- **PipeCurves** (трубы) - for vertical stacks
- **Levels** (уровни) - for floor/elevation context

### 2. Binding Logic (Логика привязки)
Determine relationships between elements:
- Which terrace belongs to which funnel
- Which funnel connects to which stack

### 3. Calculation (Расчёт)
Perform hydraulic computations:
- Calculate flow rates based on area and rain intensity
- Verify capacity against maximum allowable flow
- Summarize results by stack and section

---

## Project Structure

```
RevitExtension/
├── RevitExtension.csproj              # Project file
├── RevitExtension.addin               # Addin manifest
├── Commands/
│   └── RainFlowCalculationCommand.cs  # Main command entry point
├── Services/
│   ├── DataCollector.cs               # Collect elements from model
│   ├── TerraceBinder.cs               # Bind terraces to funnels
│   ├── StackBinder.cs                 # Bind funnels to stacks
│   └── RainFlowCalculator.cs           # Perform calculations
├── Models/
│   ├── Terrace.cs                     # Terrace data model
│   ├── RainFunnel.cs                  # Rain funnel model
│   ├── Stack.cs                       # Vertical stack model
│   └── CalculationResult.cs           # Result data model
├── UI/
│   ├── RainFlowForm.cs                # Windows Forms UI
│   └── RainFlowViewModel.cs           # UI logic
├── Tools/
│   └── UnitConverter.cs               # Convert feet to meters
└── Properties/
    └── AssemblyInfo.cs                # Assembly metadata
```

---

## .csproj Configuration

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net48</TargetFramework>
    <UseWindowsForms>true</UseWindowsForms>
    <OutputType>Library</OutputType>
    <RootNamespace>RevitExtension</RootNamespace>
    <PlatformTarget>x64</PlatformTarget>
  </PropertyGroup>
  <ItemGroup>
    <Reference Include="RevitAPI">
      <HintPath>C:\Program Files\Autodesk\Revit 2025\RevitAPI.dll</HintPath>
      <Private>false</Private>
    </Reference>
    <Reference Include="RevitAPIUI">
      <HintPath>C:\Program Files\Autodesk\Revit 2025\RevitAPIUI.dll</HintPath>
      <Private>false</Private>
    </Reference>
  </ItemGroup>
</Project>
```

---

## Algorithm Steps

### Step 1: Find Terraces (Поиск террас)

**Goal**: Identify rooms that are terraces/balconies.

**Implementation**:
```csharp
// Get all rooms using FilteredElementCollector
var roomCollector = new FilteredElementCollector(doc)
    .OfCategory(BuiltInCategory.OST_Rooms)
    .WhereElementIsNotElementType();

// Filter by name using configurable keywords
var terraceKeywords = new[] { "терраса", "лоджия", "balcony", "terrace", "roof terrace" };

var terraces = roomCollector
    .Cast<Room>()
    .Where(r => IsTerrace(r, terraceKeywords))
    .ToList();

bool IsTerrace(Room room, string[] keywords)
{
    var roomName = room.Name?.ToLower() ?? "";
    return keywords.Any(k => roomName.Contains(k.ToLower()));
}
```

**Notes**:
- Use a configurable/customizable keyword list (not hardcoded)
- Store keywords in a settings file or input dialog
- Consider using room properties/parameters for more reliable identification

---

### Step 2: Get Area (Получение площади)

**Goal**: Extract room area and convert to square meters.

**Implementation**:
```csharp
// Room.Area returns value in square feet
double GetAreaInSquareMeters(Room room)
{
    double areaInSquareFeet = room.Area;
    // Convert to square meters (1 sq ft = 0.092903 sq m)
    return areaInSquareFeet * 0.092903;
}

// Or use UnitConverter
double areaM2 = UnitUtils.Convert(room.Area, DisplayUnitType.DUT_SQUARE_FEET, 
                                   DisplayUnitType.DUT_SQUARE_METERS);
```

**Notes**:
- Revit internally uses feet for area calculations
- Always convert to metric (m²) for calculations
- Use `UnitUtils.Convert()` for proper unit handling

---

### Step 3: Find Rain Funnels (Поиск воронок)

**Goal**: Identify rain funnel elements in the model.

**Implementation**:
```csharp
// Find PlumbingFixtures - these include rain funnels
var funnelCollector = new FilteredElementCollector(doc)
    .OfCategory(BuiltInCategory.OST_PlumbingFixtures)
    .WhereElementIsNotElementType();

var funnels = funnelCollector
    .Cast<FamilyInstance>()
    .Where(f => IsRainFunnel(f))
    .ToList();

bool IsRainFunnel(FamilyInstance instance)
{
    // Filter by family name or parameter
    var familyName = instance.Symbol?.FamilyName?.ToLower() ?? "";
    return familyName.Contains("воронка") || 
           familyName.Contains("rain") ||
           familyName.Contains("funnel");
}
```

**Notes**:
- Category `OST_PlumbingFixtures` includes various plumbing fixtures
- Filter by family name or a specific parameter to identify rain funnels
- Some models may have incorrect/missing family names - consider adding a parameter for identification

---

### Step 4: Bind Terrace to Funnel (Привязка террасы к воронке)

**Goal**: Determine which funnel drains which terrace.

**Primary Method** (Recommended):
```csharp
// Check if funnel point is inside room boundary
bool IsFunnelInRoom(Room room, FamilyInstance funnel)
{
    XYZ funnelLocation = funnel.Location as XYZ;
    if (funnelLocation == null) return false;
    
    return room.IsPointInRoom(funnelLocation);
}
```

**Alternative Methods**:

**BoundingBox Approach**:
```csharp
bool IsFunnelInRoomByBoundingBox(Room room, FamilyInstance funnel)
{
    BoundingBoxXYZ roomBB = room.get_BoundingBox(null);
    BoundingBoxXYZ funnelBB = funnel.get_BoundingBox(null);
    
    if (roomBB == null || funnelBB == null) return false;
    
    return roomBB.Contains(funnelBB.Min) || roomBB.Contains(funnelBB.Max);
}
```

**Nearest Funnel Approach** (Less Accurate):
```csharp
FamilyInstance FindNearestFunnel(Room room, IEnumerable<FamilyInstance> funnels)
{
    XYZ roomCenter = GetRoomCenter(room);
    return funnels
        .OrderBy(f => GetDistance(roomCenter, GetFunnelLocation(f)))
        .FirstOrDefault();
}
```

**Notes**:
- `Room.IsPointInRoom()` is the most reliable method
- Requires properly closed room boundaries
- BoundingBox approach is less accurate but more tolerant of geometry issues

---

### Step 5: Calculate Facade Area (Учёт фасада)

**Goal**: Include vertical wall area above the funnel in flow calculation.

**Implementation**:
```csharp
// Calculate additional facade area contribution
double CalculateFacadeAreaContribution(
    double terraceLevel, 
    double buildingTopLevel,
    double influenceWidth)
{
    double facadeHeight = buildingTopLevel - terraceLevel;
    return facadeHeight * influenceWidth;
}
```

**Notes**:
- Add vertical wall area above the terrace to account for rain hitting the facade
- Typically calculated as: height from terrace level to building top × influence width
- Use configurable coefficient or user-specified parameter
- Influence width can be based on typical catchment area (e.g., 2-3 meters)

---

### Step 6: Calculate Flow Rate (Расчёт расхода)

**Goal**: Compute rain water flow using the formula Q = q × F

**Formula**:
```
Q = q × F × ψ

Where:
- Q = Flow rate (liters/second or m³/s)
- q = Rain intensity (L/s·m² or according to local code)
- F = Total catchment area (m²) = terrace area + facade area
- ψ = Runoff coefficient (dimensionless, typically 0.3-0.9 for terraces)
```

**Implementation**:
```csharp
public double CalculateFlowRate(
    double terraceAreaM2, 
    double facadeAreaM2, 
    double rainIntensity, 
    double runoffCoefficient)
{
    double totalArea = terraceAreaM2 + facadeAreaM2;
    return rainIntensity * totalArea * runoffCoefficient;
}

// Example values:
// Rain intensity q = 0.048 L/s·m² (for heavy rain - adjust per local code)
// Runoff coefficient ψ = 0.9 for terraces (impermeable surface)
```

**Notes**:
- Rain intensity depends on local climate/standards (e.g., SP 30.13330, SNiP)
- Runoff coefficient varies by surface type:
  - Concrete/roofing: 0.9-1.0
  - Gravel/ballast: 0.6-0.7
  - Green roof: 0.3-0.5

---

### Step 7: Determine Stacks (Определение стояков)

**Goal**: Identify vertical pipes that receive flow from funnels.

**Implementation**:
```csharp
// Find vertical pipes (stacks)
var pipeCollector = new FilteredElementCollector(doc)
    .OfCategory(BuiltInCategory.OST_PipeCurves)
    .WhereElementIsNotElementType();

var stacks = pipeCollector
    .Cast<Pipe>()
    .Where(p => IsVerticalStack(p))
    .ToList();

bool IsVerticalStack(Pipe pipe)
{
    // Check if pipe is primarily vertical
    var startPoint = pipe.Location as LocationCurve;
    if (startPoint == null) return false;
    
    XYZ start = startPoint.Curve.GetEndPoint(0);
    XYZ end = startPoint.Curve.GetEndPoint(1);
    
    double zDiff = Math.Abs(end.Z - start.Z);
    double length = startPoint.Curve.Length;
    
    // Consider vertical if angle > 80 degrees from horizontal
    return zDiff / length > 0.98;
}
```

**Alternative**: Use MEP Systems to identify stack groups:
```csharp
// Group pipes by MEP system
var stackSystems = pipeCollector
    .Cast<Pipe>()
    .Select(p => p.MEPModel?.MechanicalSystem)
    .Where(s => s != null && s.Name.Contains("Водосток"))
    .Distinct();
```

**Notes**:
- Filter by pipe direction or use MEP system information
- Check for system type "Water Supply" or custom parameter
- May need to filter by pipe diameter (stacks are typically DN70-DN150)

---

### Step 8: Group Funnels by Stack (Группировка воронок по стоякам)

**Goal**: Associate each funnel with its downstream stack.

**Implementation**:
```csharp
// Option 1: By connection (most accurate)
var funnelToStack = new Dictionary<ElementId, ElementId>();

foreach (var funnel in funnels)
{
    var connector = GetConnectors(funnel).FirstOrDefault();
    if (connector != null)
    {
        var connectedElement = connector.Owner;
        if (connectedElement is Pipe)
        {
            funnelToStack[funnel.Id] = connectedElement.Id;
        }
    }
}

// Option 2: By proximity (if connections unavailable)
var funnelStackMapping = funnels
    .Select(f => new 
    { 
        Funnel = f,
        Stack = stacks.OrderBy(s => GetDistance(f, s)).First()
    })
    .ToDictionary(x => x.Funnel.Id, x => x.Stack.Id);
```

**Notes**:
- Use connector information for accurate binding
- Fall back to proximity if connection data is unavailable
- May need to traverse pipe network to find the main stack

---

### Step 9: Group by Section (Группировка по секциям)

**Goal**: Organize stacks by building section/facade.

**Implementation**:
```csharp
// Group stacks by section parameter
var stacksBySection = stacks
    .GroupBy(s => GetSectionParameter(s))
    .ToDictionary(g => g.Key, g => g.ToList());

string GetSectionParameter(Stack stack)
{
    // Try to get section from parameter
    Parameter sectionParam = stack.get_Parameter("Секция");
    if (sectionParam != null && sectionParam.HasValue)
        return sectionParam.AsString();
    
    // Fallback: determine by location/coordinate
    return DetermineSectionByLocation(stack);
}
```

**Notes**:
- Use a dedicated parameter (e.g., "Секция" or "Section") on stack elements
- If parameter doesn't exist, determine by location (X/Y coordinates)
- Building sections typically correspond to different facades

---

### Step 10: Verify Capacity (Проверка пропускной способности)

**Goal**: Compare calculated flow vs. maximum allowable flow.

**Implementation**:
```csharp
public CapacityCheckResult VerifyCapacity(
    double calculatedFlow, 
    FamilyInstance funnel)
{
    // Get maximum flow from family parameter
    double maxFlow = GetMaxFlowFromFamily(funnel);
    
    bool isOverloaded = calculatedFlow > maxFlow;
    
    return new CapacityCheckResult
    {
        CalculatedFlow = calculatedFlow,
        MaxFlow = maxFlow,
        IsOverloaded = isOverloaded,
        Status = isOverloaded ? "Перегрузка" : "Норма"
    };
}

double GetMaxFlowFromFamily(FamilyInstance funnel)
{
    Parameter maxFlowParam = funnel.get_Parameter("Макс_расход");
    if (maxFlowParam != null && maxFlowParam.HasValue)
        return maxFlowParam.AsDouble();
    
    // Fallback: use table lookup based on funnel type/size
    return GetDefaultMaxFlow(funnel.Symbol.FamilyName);
}
```

**Notes**:
- Add "Макс_расход" (MaxFlow) parameter to family definition
- Maximum flow depends on funnel size/type (typically 3-12 L/s)
- Display clear indication: "OK" or "OVERLOAD"

---

### Step 11: Output Results (Вывод результата)

**Goal**: Display results to user in a clear format.

**Output Data Structure**:
```csharp
public class CalculationResult
{
    public string TerraceName { get; set; }
    public double TerraceArea { get; set; }          // m²
    public string FunnelName { get; set; }
    public string StackId { get; set; }
    public string Section { get; set; }
    public double CalculatedFlow { get; set; }       // L/s
    public double MaxFlow { get; set; }              // L/s
    public string Status { get; set; }               // "Норма" or "Перегрузка"
}
```

**Display Options**:
1. **DataGridView** in Windows Forms - sortable table
2. **TaskDialog** - simple popup with summary
3. **Excel export** - detailed report
4. **Visual highlighting** - color elements in model (green=OK, red=overload)

**Visual Indication in Model** (Optional):
```csharp
// Use transaction to modify element colors
using (var tx = new Transaction(doc, "Highlight Results"))
{
    tx.Start();
    
    // Change element color based on status
    foreach (var result in results)
    {
        if (result.Status == "Перегруз")
            SetElementColor(result.FunnelId, Color.Red);
    }
    
    tx.Commit();
}
```

---

## User Workflow (Сценарий работы пользователя)

1. **Launch Plugin**: User selects the plugin from Revit ribbon or Add-Ins tab
2. **Select Floors** (Optional): User selects which levels to process
3. **Configuration** (Optional): User adjusts:
   - Terrace identification keywords
   - Rain intensity value
   - Runoff coefficient
   - Facade influence parameters
4. **Processing**:
   - Plugin finds all terraces on selected floors
   - Plugin identifies rain funnels
   - Plugin binds terraces to funnels
   - Plugin calculates flow rates
   - Plugin groups by stacks and sections
5. **View Results**: Plugin displays results table
6. **Optional**: Export to Excel or highlight overloaded elements

---

## Common Problems and Solutions

### 1. Model Data Issues (Ошибки в моделях)
- **Symptom**: Terraces not found, wrong rooms detected
- **Cause**: Inconsistent naming, missing rooms, incorrect boundaries
- **Solution**: 
  - Add custom parameter for terrace identification
  - Validate room boundaries before processing
  - Provide keyword configuration dialog

### 2. Funnel Location (Воронки могут не попадать точно в границы)
- **Symptom**: Funnel not bound to any terrace
- **Cause**: Funnel placed slightly outside room boundary
- **Solution**:
  - Use BoundingBox method as fallback
  - Add tolerance (e.g., 0.5m buffer)
  - Allow manual binding override

### 3. Stack Structure (Сложная структура стояков)
- **Symptom**: Incorrect funnel-to-stack binding
- **Cause**: Complex pipe networks, multiple connections
- **Solution**:
  - Follow pipe connections through the system
  - Use MEP system hierarchy
  - Allow user to specify stack manually

### 4. Unit Conversion (Необходимость перевода единиц)
- **Symptom**: Incorrect calculations, values off by factor
- **Cause**: Using feet instead of meters, wrong unit handling
- **Solution**:
  - Always use `UnitUtils.Convert()` for unit handling
  - Document expected units in UI (m², L/s)
  - Validate input/output units

---

## Development Recommendations

### Phase 1: Simplified Version
Start with a basic implementation:
- Process single floor only
- Simple terrace-to-funnel binding (nearest)
- Basic flow calculation
- Simple output (TaskDialog)

### Phase 2: Add Family Parameters
Enhance family definitions:
- Add "Макс_расход" (MaxFlow) parameter to funnel families
- Add "Секция" (Section) parameter to pipe families
- Add custom identification parameter for terraces

### Phase 3: Advanced Features
- Multi-floor processing with level selection
- User-configurable calculation parameters
- Excel report export
- Visual highlighting in model

### Debugging Tips
- Use `TaskDialog.Show()` for quick debugging output
- Visualize intermediate data in model (color code elements)
- Log detailed error messages with element IDs
- Test with simplified/small model first

---

## Coding Best Practices

### Transaction Management
```csharp
[Transaction(TransactionMode.Manual)]
public class RainFlowCalculationCommand : IExternalCommand
{
    public Result Execute(
        ExternalCommandData commandData,
        ref string message,
        ElementSet elements)
    {
        var doc = commandData.Application.ActiveUIDocument.Document;
        
        using (var tx = new Transaction(doc, "Calculate Rain Flow"))
        {
            try
            {
                tx.Start();
                
                // Run calculation
                var results = CalculateRainFlow(doc);
                
                tx.Commit();
                
                // Show results (outside transaction)
                ShowResults(results);
                
                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                tx.RollBack();
                message = ex.Message;
                return Result.Failed;
            }
        }
    }
}
```

### Element Access
```csharp
// Use FilteredElementCollector for efficiency
var collector = new FilteredElementCollector(doc)
    .OfCategory(BuiltInCategory.OST_Rooms)
    .WhereElementIsNotElementType();

// Always check for null
var element = doc.GetElement(elementId);
if (element == null) return;
```

### Error Handling
- Catch specific exceptions
- Log element IDs for debugging
- Provide meaningful error messages
- Continue processing on non-critical errors

---

## Deployment

### Manual Installation
1. Build in Release configuration
2. Copy DLL to: `%APPDATA%\Autodesk\Revit\Addins\2025\`
3. Copy .addin manifest to same location

### Project Structure for Deployment
```
%APPDATA%\Autodesk\Revit\Addins\2025\
├── RevitExtension.dll
└── RevitExtension.addin
```

---

## Key Revit API Categories

| Category | BuiltInCategory | Description |
|----------|------------------|-------------|
| Rooms | OST_Rooms | Room elements |
| Plumbing Fixtures | OST_PlumbingFixtures | Funnels, sinks, etc. |
| Pipe Curves | OST_PipeCurves | Pipe segments |
| Levels | OST_Levels | Floor/level definitions |
| Walls | OST_Walls | Wall elements |
| Roofs | OST_Roofs | Roof elements |

---

## Additional Resources

- Revit API Docs: https://www.revitapidocs.com/
- Autodesk Developer Network: https://www.autodesk.com/developer
- Russian building codes: SP 30.13330 (СНиП 2.04.01-85) - Water supply calculations

---

## Namespace Convention

```csharp
namespace RevitExtension.Commands { }
namespace RevitExtension.Services { }
namespace RevitExtension.Models { }
namespace RevitExtension.UI { }
namespace RevitExtension.Tools { }
```