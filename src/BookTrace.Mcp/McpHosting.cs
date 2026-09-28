using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Routing;
using Microsoft.Extensions.DependencyInjection;
using ModelContextProtocol.AspNetCore;

namespace BookTrace.Mcp;

public static class McpHosting
{
    public static IServiceCollection AddBookTraceMcp(this IServiceCollection services)
    {
        services.AddMcpServer()
            .WithHttpTransport(options => options.SessionMode = HttpServerSessionMode.Stateless)
            .WithTools<BookTools>();
        return services;
    }

    public static void MapBookTraceMcp(this IEndpointRouteBuilder endpoints) => endpoints.MapMcp("/mcp");
}
